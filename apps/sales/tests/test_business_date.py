from datetime import datetime, timedelta, timezone as datetime_timezone
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from apps.branches.models import Branch
from apps.cash.models import CashMovement, CashRegister
from apps.cash.services import open_cash_register
from apps.inventory.models import InventoryMovement, Stock
from apps.products.models import Product
from apps.sales.models import Sale
from apps.sales.services import add_sale_item, confirm_sale, create_sale
from apps.settings_app.models import BusinessDateSettings
from apps.users.models import User


class SaleBusinessDateTests(TestCase):
	def setUp(self):
		self.branch = Branch.objects.create(name="Central", code="CENTRAL")
		self.user = User.objects.create_user(username="cajero", role=User.ROLE_CAJERO, branch=self.branch)
		self.product = Product.objects.create(name="Producto", sku="PRODUCTO", list_price=Decimal("10.00"))
		self.stock = Stock.objects.create(product=self.product, branch=self.branch, quantity=5)
		self.historical_date = timezone.localdate() - timedelta(days=4)

	def enable_historical(self, business_date=None):
		BusinessDateSettings.objects.filter(pk=1).update(
			mode=BusinessDateSettings.MODE_HISTORICAL,
			business_date=business_date or self.historical_date,
		)

	def create_draft(self):
		sale = create_sale(user=self.user)
		add_sale_item(sale=sale, product=self.product, quantity=1, user=self.user)
		return sale

	def test_historical_sale_uses_cash_date_and_keeps_real_confirmation(self):
		self.enable_historical()
		register = open_cash_register(user=self.user, opening_amount=Decimal("100.00"))
		sale = self.create_draft()
		before = timezone.now()
		confirm_sale(sale=sale, user=self.user, payment_method=Sale.PAYMENT_CASH, cash_received=Decimal("10.00"))
		after = timezone.now()
		sale.refresh_from_db()
		self.stock.refresh_from_db()
		self.assertEqual(sale.business_date, register.business_date)
		self.assertEqual(sale.business_date, self.historical_date)
		self.assertEqual(timezone.localdate(sale.completed_at), self.historical_date)
		self.assertLessEqual(before, sale.confirmed_at)
		self.assertLessEqual(sale.confirmed_at, after)
		self.assertEqual(sale.inventory_movement.movement_date, self.historical_date)
		self.assertEqual(sale.cash_movement.cash_register_id, register.pk)
		self.assertEqual(self.stock.quantity, 4)
		self.client.force_login(self.user)
		response = self.client.get(reverse("sales:detail", args=[sale.pk]))
		self.assertContains(response, self.historical_date.strftime("%d/%m/%Y"))
		self.assertContains(response, "Confirmación real")
		self.assertContains(response, timezone.localtime(sale.confirmed_at).strftime("%d/%m/%Y %H:%M"))

	def test_historical_pos_rejects_manipulated_date(self):
		self.enable_historical()
		open_cash_register(user=self.user, opening_amount=Decimal("100.00"))
		sale = self.create_draft()
		self.client.force_login(self.user)
		response = self.client.get(reverse("sales:pos"))
		self.assertContains(response, f'value="{self.historical_date.isoformat()}"')
		self.assertContains(response, "readonly")
		self.assertContains(response, "La fecha corresponde a la caja")
		response = self.client.post(reverse("sales:checkout"), {
			"sale_date": timezone.localdate().isoformat(),
			"payment_method": Sale.PAYMENT_CASH,
			"cash_received": "10.00",
		}, follow=True)
		self.assertContains(response, "La fecha de venta debe coincidir con la fecha de negocio de la caja.")
		sale.refresh_from_db()
		self.stock.refresh_from_db()
		self.assertEqual(sale.status, Sale.STATUS_DRAFT)
		self.assertEqual(self.stock.quantity, 5)
		self.assertFalse(InventoryMovement.objects.exists())
		self.assertFalse(CashMovement.objects.filter(movement_type=CashMovement.TYPE_SALE).exists())
		response = self.client.post(reverse("sales:checkout"), {
			"sale_date": self.historical_date.isoformat(),
			"payment_method": Sale.PAYMENT_CASH,
			"cash_received": "10.00",
		})
		self.assertRedirects(response, reverse("sales:detail", args=[sale.pk]))
		sale.refresh_from_db()
		self.assertEqual(sale.business_date, self.historical_date)

	def test_legacy_open_register_without_business_date_cannot_sell_in_historical_mode(self):
		register = CashRegister.objects.create(user=self.user, branch=self.branch, opening_amount=Decimal("100.00"))
		self.enable_historical()
		sale = self.create_draft()
		with self.assertRaisesMessage(ValidationError, "La caja no tiene fecha de negocio"):
			confirm_sale(sale=sale, user=self.user, payment_method=Sale.PAYMENT_QR)
		self.client.force_login(self.user)
		response = self.client.get(reverse("sales:pos"))
		self.assertContains(response, "La caja no tiene fecha de negocio.")
		response = self.client.post(reverse("sales:checkout"), {
			"sale_date": self.historical_date.isoformat(), "payment_method": Sale.PAYMENT_QR,
		}, follow=True)
		self.assertContains(response, "La caja no tiene fecha de negocio.")
		register.refresh_from_db()
		self.assertIsNone(register.business_date)
		self.assertFalse(InventoryMovement.objects.exists())

	def test_historical_sale_rejects_register_with_different_global_date(self):
		self.enable_historical()
		open_cash_register(user=self.user, opening_amount=Decimal("100.00"))
		sale = self.create_draft()
		self.enable_historical(self.historical_date - timedelta(days=1))
		with self.assertRaisesMessage(ValidationError, "no coincide con la fecha de trabajo"):
			confirm_sale(sale=sale, user=self.user, payment_method=Sale.PAYMENT_QR)
		self.assertFalse(InventoryMovement.objects.exists())

	def test_insufficient_stock_rolls_back_historical_sale(self):
		self.enable_historical()
		open_cash_register(user=self.user, opening_amount=Decimal("100.00"))
		sale = self.create_draft()
		Stock.objects.filter(pk=self.stock.pk).update(quantity=0)
		with self.assertRaisesMessage(ValidationError, "Existencia insuficiente"):
			confirm_sale(sale=sale, user=self.user, payment_method=Sale.PAYMENT_QR)
		sale.refresh_from_db()
		self.stock.refresh_from_db()
		self.assertEqual(sale.status, Sale.STATUS_DRAFT)
		self.assertIsNone(sale.business_date)
		self.assertIsNone(sale.confirmed_at)
		self.assertEqual(self.stock.quantity, 0)
		self.assertFalse(InventoryMovement.objects.exists())
		self.assertFalse(CashMovement.objects.filter(movement_type=CashMovement.TYPE_SALE).exists())

	def test_automatic_mode_keeps_selected_date_behavior(self):
		open_cash_register(user=self.user, opening_amount=Decimal("100.00"))
		sale = self.create_draft()
		before = timezone.now()
		confirm_sale(sale=sale, user=self.user, payment_method=Sale.PAYMENT_QR, sale_date=self.historical_date)
		sale.refresh_from_db()
		self.assertEqual(sale.business_date, self.historical_date)
		self.assertEqual(timezone.localdate(sale.completed_at), self.historical_date)
		self.assertGreaterEqual(sale.confirmed_at, before)
		self.assertEqual(sale.inventory_movement.movement_date, timezone.localdate())


class SaleBusinessDateMigrationTests(TransactionTestCase):
	def test_preserves_legacy_timestamp_and_backfills_local_business_date(self):
		executor = MigrationExecutor(connection)
		latest_targets = executor.loader.graph.leaf_nodes()
		old_target = [("sales", "0003_sale_customer")]
		try:
			executor.migrate(old_target)
			old_apps = executor.loader.project_state(old_target).apps
			branch = old_apps.get_model("branches", "Branch").objects.create(name="Antigua", code="OLD")
			user = old_apps.get_model("users", "User").objects.create(username="legacy-sale", branch=branch, role="cajero")
			register = old_apps.get_model("cash", "CashRegister").objects.create(user=user, branch=branch, opening_amount=Decimal("10.00"))
			sale_model = old_apps.get_model("sales", "Sale")
			completed_at = datetime(2026, 11, 2, 1, 0, tzinfo=datetime_timezone.utc)
			sale = sale_model.objects.create(
				number="V-OLD", user=user, branch=branch, cash_register=register, status="COMPLETED", completed_at=completed_at,
			)
			draft = sale_model.objects.create(number="V-DRAFT", user=user, branch=branch, cash_register=register, status="DRAFT")
			executor = MigrationExecutor(connection)
			executor.migrate(latest_targets)
			new_apps = executor.loader.project_state(latest_targets).apps
			new_sale_model = new_apps.get_model("sales", "Sale")
			migrated = new_sale_model.objects.get(pk=sale.pk)
			self.assertEqual(migrated.completed_at, completed_at)
			self.assertEqual(migrated.business_date, timezone.localtime(completed_at).date())
			self.assertIsNone(migrated.confirmed_at)
			self.assertIsNone(new_sale_model.objects.get(pk=draft.pk).business_date)
		finally:
			MigrationExecutor(connection).migrate(latest_targets)

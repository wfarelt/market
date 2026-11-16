from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from apps.branches.models import Branch
from apps.cash.services import open_cash_register
from apps.inventory.models import InventoryMovement, Stock
from apps.products.models import Product
from apps.purchases.models import Purchase, PurchaseItem
from apps.purchases.services import confirm_purchase
from apps.reports.selectors import get_report_summary
from apps.sales.models import Sale
from apps.sales.services import add_sale_item, confirm_sale, create_sale
from apps.settings_app.models import BusinessDateSettings
from apps.users.models import User


class PurchaseBusinessDateTests(TestCase):
	def setUp(self):
		self.branch = Branch.objects.create(name="Central", code="CENTRAL")
		self.user = User.objects.create_user(username="admin", role=User.ROLE_ADMIN, branch=self.branch)
		self.product = Product.objects.create(name="Producto", sku="PRODUCTO", cost_price=Decimal("3.00"), list_price=Decimal("10.00"))
		self.historical_date = timezone.localdate() - timedelta(days=5)

	def enable_historical(self):
		BusinessDateSettings.objects.filter(pk=1).update(
			mode=BusinessDateSettings.MODE_HISTORICAL, business_date=self.historical_date,
		)

	def create_purchase(self, purchase_date):
		purchase = Purchase.objects.create(branch=self.branch, purchase_date=purchase_date, created_by=self.user)
		PurchaseItem.objects.create(
			purchase=purchase, product=self.product, quantity=Decimal("3"),
			unit_cost=Decimal("5.00"), sale_price=Decimal("12.00"), update_cost=True,
		)
		return purchase

	def test_historical_purchase_uses_work_date_and_preserves_real_confirmation(self):
		self.enable_historical()
		purchase = self.create_purchase(self.historical_date)
		before = timezone.now()
		confirm_purchase(purchase=purchase, user=self.user)
		after = timezone.now()
		purchase.refresh_from_db()
		self.product.refresh_from_db()
		self.assertEqual(purchase.business_date, self.historical_date)
		self.assertEqual(purchase.purchase_date, self.historical_date)
		self.assertEqual(purchase.inventory_movement.movement_date, self.historical_date)
		self.assertEqual(Stock.objects.get(branch=self.branch, product=self.product).quantity, 3)
		self.assertEqual(self.product.cost_price, Decimal("5.00"))
		self.assertLessEqual(before, purchase.confirmed_at)
		self.assertLessEqual(purchase.confirmed_at, after)
		self.assertLessEqual(before, purchase.inventory_movement.created_at)
		self.assertLessEqual(purchase.inventory_movement.created_at, after)
		with self.assertRaisesMessage(ValidationError, "Solo se pueden confirmar compras en borrador"):
			confirm_purchase(purchase=purchase, user=self.user)
		self.assertEqual(Stock.objects.get(branch=self.branch, product=self.product).quantity, 3)

	def test_other_date_draft_cannot_be_confirmed_and_can_be_corrected(self):
		self.enable_historical()
		purchase = self.create_purchase(self.historical_date - timedelta(days=1))
		with self.assertRaisesMessage(ValidationError, "La fecha de compra debe coincidir con la fecha de trabajo"):
			confirm_purchase(purchase=purchase, user=self.user)
		purchase.refresh_from_db()
		self.product.refresh_from_db()
		self.assertEqual(purchase.status, Purchase.STATUS_DRAFT)
		self.assertIsNone(purchase.business_date)
		self.assertIsNone(purchase.confirmed_at)
		self.assertFalse(Stock.objects.exists())
		self.assertFalse(InventoryMovement.objects.exists())
		self.assertEqual(self.product.cost_price, Decimal("3.00"))
		purchase.purchase_date = self.historical_date
		purchase.save(update_fields=["purchase_date"])
		confirm_purchase(purchase=purchase, user=self.user)
		purchase.refresh_from_db()
		self.assertEqual(purchase.business_date, self.historical_date)

	def test_automatic_purchase_keeps_existing_date_and_report_behavior(self):
		purchase = self.create_purchase(self.historical_date)
		confirm_purchase(purchase=purchase, user=self.user)
		purchase.refresh_from_db()
		self.assertEqual(purchase.purchase_date, self.historical_date)
		self.assertEqual(purchase.business_date, timezone.localdate(purchase.confirmed_at))
		self.assertEqual(purchase.inventory_movement.movement_date, timezone.localdate())
		self.assertEqual(get_report_summary(user=self.user, start_date=self.historical_date, end_date=self.historical_date)["purchases_count"], 0)
		self.assertEqual(get_report_summary(user=self.user, start_date=timezone.localdate(), end_date=timezone.localdate())["purchases_count"], 1)

	def test_historical_web_form_defaults_date_and_confirm_rejects_mismatch(self):
		self.enable_historical()
		self.client.force_login(self.user)
		response = self.client.get(reverse("purchases:create"))
		self.assertContains(response, f'value="{self.historical_date.isoformat()}"')
		self.assertContains(response, "la fecha de compra debe coincidir con la fecha de trabajo")
		purchase = self.create_purchase(self.historical_date - timedelta(days=1))
		response = self.client.post(reverse("purchases:confirm", args=[purchase.pk]), follow=True)
		self.assertContains(response, "La fecha de compra debe coincidir con la fecha de trabajo")
		self.assertContains(response, "Fecha de negocio: No determinada")
		self.assertContains(response, "Confirmación real: No disponible")
		self.assertFalse(InventoryMovement.objects.exists())
		response = self.client.get(reverse("purchases:update", args=[purchase.pk]))
		self.assertContains(response, (self.historical_date - timedelta(days=1)).isoformat())

	def test_historical_web_creation_and_confirmation(self):
		self.enable_historical()
		self.client.force_login(self.user)
		response = self.client.post(reverse("purchases:create"), {
			"purchase_date": self.historical_date.isoformat(),
			"invoice_number": "FAC-001",
			"items-TOTAL_FORMS": "1",
			"items-INITIAL_FORMS": "0",
			"items-MIN_NUM_FORMS": "0",
			"items-MAX_NUM_FORMS": "1000",
			"items-0-product": str(self.product.pk),
			"items-0-quantity": "3",
			"items-0-unit_cost": "5.00",
			"items-0-sale_price": "12.00",
		})
		purchase = Purchase.objects.get(invoice_number="FAC-001")
		self.assertRedirects(response, reverse("purchases:detail", args=[purchase.pk]))
		response = self.client.post(reverse("purchases:confirm", args=[purchase.pk]), follow=True)
		purchase.refresh_from_db()
		self.assertContains(response, f'Fecha de negocio: {self.historical_date.strftime("%d/%m/%Y")}')
		self.assertContains(response, "Confirmación real:")
		self.assertEqual(purchase.business_date, self.historical_date)
		self.assertEqual(purchase.inventory_movement.movement_date, self.historical_date)

	def test_pending_purchase_enables_historical_sale(self):
		self.enable_historical()
		open_cash_register(user=self.user, opening_amount=Decimal("100.00"))
		sale = create_sale(user=self.user)
		add_sale_item(sale=sale, product=self.product, quantity=1, user=self.user)
		with self.assertRaisesMessage(ValidationError, "Existencia insuficiente"):
			confirm_sale(sale=sale, user=self.user, payment_method=Sale.PAYMENT_QR)
		self.assertFalse(InventoryMovement.objects.exists())
		purchase = self.create_purchase(self.historical_date)
		confirm_purchase(purchase=purchase, user=self.user)
		confirm_sale(sale=sale, user=self.user, payment_method=Sale.PAYMENT_QR)
		sale.refresh_from_db()
		purchase.refresh_from_db()
		self.assertEqual(Stock.objects.get(branch=self.branch, product=self.product).quantity, 2)
		self.assertEqual(sale.business_date, self.historical_date)
		self.assertEqual(purchase.business_date, self.historical_date)
		self.assertEqual(sale.inventory_movement.movement_date, self.historical_date)
		self.assertEqual(purchase.inventory_movement.movement_date, self.historical_date)
		self.assertIsNotNone(sale.inventory_movement.posted_at)
		self.assertIsNotNone(purchase.inventory_movement.posted_at)


class PurchaseBusinessDateMigrationTests(TransactionTestCase):
	def test_existing_purchase_remains_unchanged_with_unknown_business_date(self):
		executor = MigrationExecutor(connection)
		latest_targets = executor.loader.graph.leaf_nodes()
		old_target = [("purchases", "0004_supplier_purchase_purchase_header")]
		try:
			executor.migrate(old_target)
			old_apps = executor.loader.project_state(old_target).apps
			branch = old_apps.get_model("branches", "Branch").objects.create(name="Antigua", code="OLD")
			confirmed_at = timezone.now()
			purchase = old_apps.get_model("purchases", "Purchase").objects.create(
				number="C-OLD", branch=branch, status="CONFIRMED",
				purchase_date=timezone.localdate() - timedelta(days=3), confirmed_at=confirmed_at,
			)
			executor = MigrationExecutor(connection)
			executor.migrate(latest_targets)
			new_apps = executor.loader.project_state(latest_targets).apps
			migrated = new_apps.get_model("purchases", "Purchase").objects.get(pk=purchase.pk)
			self.assertIsNone(migrated.business_date)
			self.assertEqual(migrated.purchase_date, purchase.purchase_date)
			self.assertEqual(migrated.confirmed_at, confirmed_at)
			self.assertEqual(migrated.status, "CONFIRMED")
		finally:
			MigrationExecutor(connection).migrate(latest_targets)

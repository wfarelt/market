from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from apps.branches.models import Branch
from apps.cash.models import CashMovement, CashRegister, ExpenseCategory, PettyCashExpense
from apps.cash.services import close_cash_register, open_cash_register, register_petty_cash_expense
from apps.inventory.models import Stock
from apps.products.models import Product
from apps.reports.selectors import get_report_summary
from apps.sales.models import Sale
from apps.sales.services import add_sale_item, confirm_sale, create_sale
from apps.settings_app.models import BusinessDateSettings
from apps.users.models import User


class CashBusinessDateTests(TestCase):
	def setUp(self):
		self.branch = Branch.objects.create(name="Central", code="CENTRAL")
		self.user = User.objects.create_user(username="cajero", role=User.ROLE_CAJERO, branch=self.branch)

	def test_automatic_opening_and_closing_keep_opening_business_date(self):
		today = timezone.localdate()
		register = open_cash_register(user=self.user, opening_amount=Decimal("100.00"))
		self.assertEqual(register.business_date, today)
		self.assertEqual(timezone.localdate(register.opened_at), today)
		next_day = register.opened_at + timedelta(days=1)
		with patch("apps.cash.services.timezone.now", return_value=next_day):
			close_cash_register(cash_register=register, user=self.user, closing_amount=Decimal("100.00"))
		register.refresh_from_db()
		self.assertEqual(register.business_date, today)
		self.assertEqual(register.closed_at, next_day)
		self.assertEqual(get_report_summary(user=self.user, start_date=today, end_date=today)["closed_cash_registers"], 0)
		self.assertEqual(get_report_summary(user=self.user, start_date=today + timedelta(days=1), end_date=today + timedelta(days=1))["closed_cash_registers"], 1)

	def test_closing_total_includes_electronic_payments(self):
		register = open_cash_register(user=self.user, opening_amount=Decimal("100.00"))
		product = Product.objects.create(name="Producto", sku="PRODUCTO", list_price=Decimal("25.00"))
		Stock.objects.create(product=product, branch=self.branch, quantity=1)
		sale = create_sale(user=self.user)
		add_sale_item(sale=sale, product=product, quantity=1, user=self.user)
		confirm_sale(sale=sale, user=self.user, payment_method=Sale.PAYMENT_QR)
		close_cash_register(cash_register=register, user=self.user, closing_amount=Decimal("125.00"))
		register.refresh_from_db()
		self.assertEqual(register.expected_amount, Decimal("125.00"))
		self.assertEqual(register.difference, Decimal("0.00"))
		self.assertEqual(sale.cash_register.business_date, register.business_date)

	def test_historical_date_is_shared_by_register_movements_without_faking_timestamps(self):
		selected_date = timezone.localdate() - timedelta(days=5)
		BusinessDateSettings.objects.filter(pk=1).update(
			mode=BusinessDateSettings.MODE_HISTORICAL, business_date=selected_date,
		)
		before = timezone.now()
		first = open_cash_register(user=self.user, opening_amount=Decimal("100.00"))
		category = ExpenseCategory.objects.create(name="Otros")
		expense = register_petty_cash_expense(
			cash_register=first, category=category, concept="Gasto",
			amount=Decimal("10.00"), user=self.user,
		)
		close_cash_register(cash_register=first, user=self.user, closing_amount=Decimal("90.00"))
		first.refresh_from_db()
		second = open_cash_register(user=self.user, opening_amount=Decimal("90.00"))
		after = timezone.now()
		self.assertEqual((first.business_date, second.business_date), (selected_date, selected_date))
		self.assertEqual(expense.movement.cash_register.business_date, selected_date)
		self.assertEqual(first.movements.count(), 3)
		for movement in first.movements.all():
			self.assertEqual(movement.cash_register.business_date, selected_date)
			self.assertLessEqual(before, movement.created_at)
			self.assertLessEqual(movement.created_at, after)
		self.assertLessEqual(before, first.opened_at)
		self.assertLessEqual(first.closed_at, after)
		self.assertEqual(first.expected_amount, Decimal("90.00"))
		self.assertEqual(first.difference, Decimal("0.00"))
		self.assertEqual(first.movements.filter(movement_type=CashMovement.TYPE_CLOSING).count(), 1)

	def test_views_display_business_date_and_explain_combined_total(self):
		register = open_cash_register(user=self.user, opening_amount=Decimal("100.00"))
		self.client.force_login(self.user)
		for url in (reverse("cash:list"), reverse("cash:detail", args=[register.pk]), reverse("cash:close", args=[register.pk])):
			with self.subTest(url=url):
				response = self.client.get(url)
				self.assertContains(response, register.business_date.strftime("%d/%m/%Y"))
				self.assertContains(response, "Fecha de negocio")
		response = self.client.get(reverse("cash:close", args=[register.pk]))
		self.assertContains(response, "Monto total declarado")
		self.assertContains(response, "Incluye efectivo y los pagos electrónicos")
		self.assertContains(response, "Apertura real")

	def test_existing_register_with_unknown_date_is_shown_without_guessing(self):
		register = CashRegister.objects.create(user=self.user, branch=self.branch, opening_amount=Decimal("10.00"))
		self.client.force_login(self.user)
		response = self.client.get(reverse("cash:detail", args=[register.pk]))
		self.assertContains(response, "No determinada")
		self.assertContains(response, "Apertura real")

	def test_open_form_shows_business_date(self):
		self.client.force_login(self.user)
		response = self.client.get(reverse("cash:open"))
		self.assertContains(response, timezone.localdate().strftime("%d/%m/%Y"))
		self.assertContains(response, "Fecha de negocio de la nueva caja")

	def test_historical_expense_rejects_missing_or_mismatched_cash_date(self):
		selected_date = timezone.localdate() - timedelta(days=5)
		BusinessDateSettings.objects.filter(pk=1).update(mode=BusinessDateSettings.MODE_HISTORICAL, business_date=selected_date)
		register = open_cash_register(user=self.user, opening_amount=Decimal("100.00"))
		category = ExpenseCategory.objects.create(name="Otros")
		self.client.force_login(self.user)
		for business_date in (None, selected_date - timedelta(days=1)):
			with self.subTest(business_date=business_date):
				CashRegister.objects.filter(pk=register.pk).update(business_date=business_date)
				with self.assertRaisesMessage(ValidationError, "La fecha de negocio de la caja no coincide con la fecha de trabajo."):
					register_petty_cash_expense(cash_register=register, category=category, concept="Gasto", amount=Decimal("10.00"), user=self.user)
				response = self.client.post(reverse("cash:expense-create", args=[register.pk]), {
					"category": category.pk, "concept": "Gasto", "amount": "10.00",
				})
				self.assertContains(response, "La fecha de negocio de la caja no coincide con la fecha de trabajo.")
				self.assertFalse(PettyCashExpense.objects.exists())
				self.assertEqual(register.movements.count(), 1)

	def test_historical_close_allows_cash_with_unknown_or_mismatched_date(self):
		selected_date = timezone.localdate() - timedelta(days=5)
		BusinessDateSettings.objects.filter(pk=1).update(mode=BusinessDateSettings.MODE_HISTORICAL, business_date=selected_date)
		for business_date in (None, selected_date - timedelta(days=1)):
			with self.subTest(business_date=business_date):
				register = open_cash_register(user=self.user, opening_amount=Decimal("100.00"))
				CashRegister.objects.filter(pk=register.pk).update(business_date=business_date)
				close_cash_register(cash_register=register, user=self.user, closing_amount=Decimal("100.00"))
				register.refresh_from_db()
				self.assertEqual(register.status, CashRegister.STATUS_CLOSED)
				self.assertEqual(register.business_date, business_date)
				self.assertEqual(register.difference, Decimal("0.00"))

	def test_automatic_expense_accepts_legacy_cash_without_business_date(self):
		register = open_cash_register(user=self.user, opening_amount=Decimal("100.00"))
		CashRegister.objects.filter(pk=register.pk).update(business_date=None)
		category = ExpenseCategory.objects.create(name="Otros")
		expense = register_petty_cash_expense(
			cash_register=register, category=category, concept="Gasto",
			amount=Decimal("10.00"), user=self.user,
		)
		self.assertIsNone(expense.cash_register.business_date)
		self.assertEqual(expense.movement.amount, Decimal("10.00"))


class CashBusinessDateMigrationTests(TransactionTestCase):
	def test_existing_register_keeps_dates_and_has_unknown_business_date(self):
		executor = MigrationExecutor(connection)
		latest_targets = executor.loader.graph.leaf_nodes()
		old_target = [("cash", "0004_cashclosurecorrection")]
		try:
			executor.migrate(old_target)
			old_apps = executor.loader.project_state(old_target).apps
			branch = old_apps.get_model("branches", "Branch").objects.create(name="Antigua", code="OLD")
			user = old_apps.get_model("users", "User").objects.create(username="legacy", branch=branch, role="cajero")
			register = old_apps.get_model("cash", "CashRegister").objects.create(
				user=user, branch=branch, opening_amount=Decimal("25.00"),
			)
			opened_at = register.opened_at
			executor = MigrationExecutor(connection)
			executor.migrate(latest_targets)
			new_apps = executor.loader.project_state(latest_targets).apps
			migrated = new_apps.get_model("cash", "CashRegister").objects.get(pk=register.pk)
			self.assertIsNone(migrated.business_date)
			self.assertEqual(migrated.opened_at, opened_at)
			self.assertEqual(migrated.opening_amount, Decimal("25.00"))
		finally:
			MigrationExecutor(connection).migrate(latest_targets)

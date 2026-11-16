from datetime import datetime, time, timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.branches.models import Branch
from apps.cash.models import CashMovement, CashRegister
from apps.customers.models import Credit, CreditPayment, Customer
from apps.inventory.models import Stock
from apps.products.models import Product
from apps.purchases.models import Purchase, PurchaseItem
from apps.reports.selectors import DATE_BASIS_BUSINESS, DATE_BASIS_PREVIOUS, DATE_BASIS_REAL, get_report_summary
from apps.sales.models import Sale
from apps.settings_app.models import BusinessDateSettings
from apps.users.models import User


class ReportDateBasisTests(TestCase):
	def setUp(self):
		self.branch = Branch.objects.create(name="Central", code="CENTRAL")
		self.other_branch = Branch.objects.create(name="Norte", code="NORTE")
		self.admin = User.objects.create_user(username="admin", role=User.ROLE_ADMIN, branch=self.branch)
		self.superadmin = User.objects.create_user(username="super", role=User.ROLE_SUPERADMIN)
		self.today = timezone.localdate()
		self.past = self.today - timedelta(days=4)
		self.now = timezone.now()
		self.register = CashRegister.objects.create(
			user=self.admin, branch=self.branch, status=CashRegister.STATUS_CLOSED,
			opening_amount=0, closing_amount=10, expected_amount=8, difference=2,
			closed_at=self.now, business_date=self.past,
		)
		self.sale = Sale.objects.create(
			user=self.admin, branch=self.branch, cash_register=self.register, status=Sale.STATUS_COMPLETED,
			total=Decimal("50.00"), completed_at=self.now, confirmed_at=self.now, business_date=self.past,
		)
		self.purchase = Purchase.objects.create(
			branch=self.branch, status=Purchase.STATUS_CONFIRMED, confirmed_at=self.now,
			purchase_date=self.past, business_date=self.past,
		)
		self.product = Product.objects.create(name="Producto", sku="PRODUCTO")
		PurchaseItem.objects.create(purchase=self.purchase, product=self.product, quantity=2, unit_cost=5, sale_price=8)
		self.legacy_register = CashRegister.objects.create(
			user=self.admin, branch=self.branch, status=CashRegister.STATUS_CLOSED,
			opening_amount=0, closing_amount=0, expected_amount=0, difference=0, closed_at=self.now,
		)
		self.legacy_sale = Sale.objects.create(
			user=self.admin, branch=self.branch, cash_register=self.legacy_register,
			status=Sale.STATUS_COMPLETED, total=Decimal("25.00"), completed_at=self.now, business_date=self.today,
		)
		self.legacy_purchase = Purchase.objects.create(branch=self.branch, status=Purchase.STATUS_CONFIRMED, confirmed_at=self.now)
		self.client.force_login(self.admin)

	def summary(self, date_basis, day):
		return get_report_summary(user=self.admin, date_basis=date_basis, start_date=day, end_date=day)

	def test_business_period_uses_business_date_and_reports_unknowns(self):
		result = self.summary(DATE_BASIS_BUSINESS, self.past)
		self.assertEqual(result["sales_total"], Decimal("50.00"))
		self.assertEqual(result["purchases_total"], Decimal("10.00"))
		self.assertEqual(result["closed_cash_registers"], 1)
		self.assertEqual(result["cash_difference"], Decimal("2.00"))
		self.assertEqual(result["unknown_dates"], {"sales": 0, "purchases": 1, "cash_registers": 1, "credits": 0, "credit_payments": 0})
		self.assertEqual(result["unknown_dates_total"], 2)
		self.assertEqual(self.summary(DATE_BASIS_BUSINESS, self.today)["sales_total"], Decimal("25.00"))

	def test_real_period_uses_real_confirmation_and_excludes_unknown_sale(self):
		result = self.summary(DATE_BASIS_REAL, self.today)
		self.assertEqual(result["sales_total"], Decimal("50.00"))
		self.assertEqual(result["purchases_count"], 2)
		self.assertEqual(result["closed_cash_registers"], 2)
		self.assertEqual(result["unknown_dates"], {"sales": 1, "purchases": 0, "cash_registers": 0})
		self.assertEqual(self.summary(DATE_BASIS_REAL, self.past)["sales_count"], 0)

	def test_previous_basis_preserves_existing_report_behavior(self):
		result = self.summary(DATE_BASIS_PREVIOUS, self.today)
		self.assertEqual(result["sales_total"], Decimal("75.00"))
		self.assertEqual(result["purchases_count"], 2)
		self.assertEqual(result["closed_cash_registers"], 2)
		self.assertEqual(result["unknown_dates_total"], 0)
		self.assertEqual(get_report_summary(user=self.admin, start_date=self.today, end_date=self.today)["sales_total"], Decimal("75.00"))

	def test_unknown_counts_respect_branch_scope(self):
		other_user = User.objects.create_user(username="otro", role=User.ROLE_ADMIN, branch=self.other_branch)
		CashRegister.objects.create(user=other_user, branch=self.other_branch, status=CashRegister.STATUS_CLOSED, opening_amount=0)
		result = get_report_summary(user=self.admin, branch=self.other_branch, date_basis=DATE_BASIS_BUSINESS, start_date=self.past, end_date=self.past)
		self.assertEqual(result["unknown_dates_total"], 2)
		result = get_report_summary(user=self.superadmin, branch=self.other_branch, date_basis=DATE_BASIS_BUSINESS, start_date=self.past, end_date=self.past)
		self.assertEqual(result["unknown_dates"], {"sales": 0, "purchases": 0, "cash_registers": 1, "credits": 0, "credit_payments": 0})

	def test_user_without_branch_cannot_see_other_branches(self):
		user = User.objects.create_user(username="sin_sucursal", role=User.ROLE_ADMIN)
		result = get_report_summary(user=user, date_basis=DATE_BASIS_BUSINESS, start_date=self.past, end_date=self.past)
		self.assertEqual(result["sales_count"], 0)
		self.assertEqual(result["unknown_dates_total"], 0)

	def test_register_closed_after_midnight_uses_selected_basis(self):
		opened_at = timezone.make_aware(datetime.combine(self.today - timedelta(days=1), time(23, 30)))
		closed_at = timezone.make_aware(datetime.combine(self.today, time(0, 30)))
		CashRegister.objects.filter(pk=self.register.pk).update(
			opened_at=opened_at, closed_at=closed_at, business_date=self.today - timedelta(days=1),
		)
		self.assertEqual(self.summary(DATE_BASIS_BUSINESS, self.today - timedelta(days=1))["closed_cash_registers"], 1)
		self.assertEqual(self.summary(DATE_BASIS_REAL, self.today - timedelta(days=1))["closed_cash_registers"], 0)
		self.assertEqual(self.summary(DATE_BASIS_REAL, self.today)["closed_cash_registers"], 2)

	def test_credits_follow_selected_basis_and_balances_are_current(self):
		customer = Customer.objects.create(first_name="Cliente", last_name="Uno", id_document="123", created_by=self.admin)
		credit = Credit.objects.create(
			customer=customer, sale=self.sale, branch=self.branch, user=self.admin,
			original_amount=50, balance=30,
		)
		movement = CashMovement.objects.create(cash_register=self.register, movement_type=CashMovement.TYPE_CREDIT_COLLECTION, amount=20)
		CreditPayment.objects.create(credit=credit, cash_register=self.register, cash_movement=movement, user=self.admin, amount=20, business_date=self.past)
		self.product.cost_price = Decimal("5.00")
		self.product.save(update_fields=["cost_price"])
		Stock.objects.create(product=self.product, branch=self.branch, quantity=3)
		for basis in (DATE_BASIS_BUSINESS, DATE_BASIS_REAL, DATE_BASIS_PREVIOUS):
			with self.subTest(basis=basis):
				historical = self.summary(basis, self.past)
				current = self.summary(basis, self.today)
				self.assertEqual(historical["credit_issued"], 50 if basis == DATE_BASIS_BUSINESS else 0)
				self.assertEqual(historical["credit_collected"], 20 if basis == DATE_BASIS_BUSINESS else 0)
				self.assertEqual(current["credit_issued"], 0 if basis == DATE_BASIS_BUSINESS else 50)
				self.assertEqual(current["credit_collected"], 0 if basis == DATE_BASIS_BUSINESS else 20)
				self.assertEqual(historical["credit_balance"], 30)
				self.assertEqual(historical["stock_value"], 15)

	def test_business_credit_payments_use_each_payment_date(self):
		customer = Customer.objects.create(first_name="Cliente", last_name="Uno", id_document="123", created_by=self.admin)
		credit = Credit.objects.create(customer=customer, sale=self.sale, branch=self.branch, user=self.admin, original_amount=50, balance=20)
		for amount, payment_date in ((10, self.past), (20, self.today)):
			movement = CashMovement.objects.create(cash_register=self.register, movement_type=CashMovement.TYPE_CREDIT_COLLECTION, amount=amount)
			CreditPayment.objects.create(credit=credit, cash_register=self.register, cash_movement=movement, user=self.admin, amount=amount, business_date=payment_date)
		historical = self.summary(DATE_BASIS_BUSINESS, self.past)
		current = self.summary(DATE_BASIS_BUSINESS, self.today)
		self.assertEqual((historical["credit_issued"], historical["credit_collected"]), (50, 10))
		self.assertEqual((current["credit_issued"], current["credit_collected"]), (0, 20))
		self.assertEqual(self.summary(DATE_BASIS_REAL, self.today)["credit_collected"], 30)

	def test_unknown_credit_dates_are_counted_without_guessing_and_scoped_by_branch(self):
		customer = Customer.objects.create(first_name="Cliente", last_name="Uno", id_document="123", created_by=self.admin)
		Sale.objects.filter(pk=self.sale.pk).update(business_date=None)
		credit = Credit.objects.create(customer=customer, sale=self.sale, branch=self.branch, user=self.admin, original_amount=50, balance=30)
		movement = CashMovement.objects.create(cash_register=self.register, movement_type=CashMovement.TYPE_CREDIT_COLLECTION, amount=20)
		CreditPayment.objects.create(credit=credit, cash_register=self.register, cash_movement=movement, user=self.admin, amount=20)
		other_user = User.objects.create_user(username="otro", role=User.ROLE_ADMIN, branch=self.other_branch)
		other_register = CashRegister.objects.create(user=other_user, branch=self.other_branch, opening_amount=0, status=CashRegister.STATUS_CLOSED)
		other_sale = Sale.objects.create(user=other_user, branch=self.other_branch, cash_register=other_register, status=Sale.STATUS_COMPLETED, total=9, completed_at=self.now)
		other_credit = Credit.objects.create(customer=customer, sale=other_sale, branch=self.other_branch, user=other_user, original_amount=9, balance=4)
		other_movement = CashMovement.objects.create(cash_register=other_register, movement_type=CashMovement.TYPE_CREDIT_COLLECTION, amount=5)
		CreditPayment.objects.create(credit=other_credit, cash_register=other_register, cash_movement=other_movement, user=other_user, amount=5)

		result = self.summary(DATE_BASIS_BUSINESS, self.past)
		self.assertEqual(result["unknown_dates"]["credits"], 1)
		self.assertEqual(result["unknown_dates"]["credit_payments"], 1)
		self.assertEqual(result["credit_issued"], 0)
		self.assertEqual(result["credit_collected"], 0)
		self.assertEqual(result["credit_balance"], 30)
		self.assertEqual(self.summary(DATE_BASIS_BUSINESS, self.today)["unknown_dates"]["credit_payments"], 1)
		other = get_report_summary(user=self.superadmin, branch=self.other_branch, date_basis=DATE_BASIS_BUSINESS, start_date=self.past, end_date=self.past)
		self.assertEqual(other["unknown_dates"]["credits"], 1)
		self.assertEqual(other["unknown_dates"]["credit_payments"], 1)
		self.assertEqual(other["credit_balance"], 4)
		all_branches = get_report_summary(user=self.superadmin, date_basis=DATE_BASIS_BUSINESS, start_date=self.past, end_date=self.past)
		self.assertEqual(all_branches["unknown_dates"]["credits"], 2)
		self.assertEqual(all_branches["unknown_dates"]["credit_payments"], 2)
		response = self.client.get(reverse("reports:index"), {"date_basis": DATE_BASIS_BUSINESS, "start_date": self.past.isoformat(), "end_date": self.past.isoformat()})
		self.assertContains(response, "1 créditos y 1 cobros")
		self.assertContains(response, "no se puede determinar si corresponden al periodo")
		self.assertEqual(self.summary(DATE_BASIS_REAL, self.today)["credit_issued"], 50)
		self.assertEqual(self.summary(DATE_BASIS_PREVIOUS, self.today)["credit_collected"], 20)

	def test_ui_legacy_default_and_business_warning(self):
		response = self.client.get(reverse("reports:index"))
		self.assertEqual(response.context["date_basis"], DATE_BASIS_PREVIOUS)
		self.assertEqual(response.context["report"]["sales_total"], Decimal("75.00"))
		response = self.client.get(reverse("reports:index"), {
			"date_basis": DATE_BASIS_BUSINESS, "start_date": self.past.isoformat(), "end_date": self.past.isoformat(),
		})
		self.assertEqual(response.context["report"]["sales_total"], Decimal("50.00"))
		self.assertContains(response, "No se incluyen 2 registros sin fecha")
		self.assertContains(response, "no se puede determinar si corresponden al periodo")
		self.assertContains(response, "saldo de créditos y el inventario muestran valores actuales")
		self.assertContains(response, "Los créditos emitidos usan la fecha de negocio de la venta")

	def test_historical_mode_defaults_to_business_date_and_basis(self):
		BusinessDateSettings.objects.filter(pk=1).update(mode=BusinessDateSettings.MODE_HISTORICAL, business_date=self.past)
		response = self.client.get(reverse("reports:index"))
		self.assertEqual(response.context["date_basis"], DATE_BASIS_BUSINESS)
		self.assertEqual(response.context["report"]["sales_total"], Decimal("50.00"))
		self.assertContains(response, f'value="{self.past.isoformat()}"')

	def test_invalid_filter_does_not_display_success_shaped_report(self):
		for params in (
			{"date_basis": "incorrecto"},
			{"start_date": "incorrecto"},
			{"start_date": self.today.isoformat(), "end_date": self.past.isoformat()},
		):
			with self.subTest(params=params):
				response = self.client.get(reverse("reports:index"), params)
				self.assertNotIn("report", response.context)
				self.assertTrue(response.context["form"].errors)

	def test_partial_filter_displays_the_effective_defaults(self):
		response = self.client.get(reverse("reports:index"), {"date_basis": DATE_BASIS_REAL})
		self.assertEqual(response.context["date_basis"], DATE_BASIS_REAL)
		self.assertContains(response, f'value="{self.today.isoformat()}"', count=2)

	def test_superadmin_invalid_branch_is_rejected(self):
		self.client.force_login(self.superadmin)
		response = self.client.get(reverse("reports:index"), {"branch": "999999"})
		self.assertIn("branch", response.context["form"].errors)
		self.assertNotIn("report", response.context)

	def test_unknown_criterion_is_rejected_by_service(self):
		with self.assertRaises(ValueError):
			self.summary("incorrecto", self.today)

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.branches.models import Branch
from apps.cash.models import CashMovement, CashRegister
from apps.cash.services import close_cash_register, open_cash_register
from apps.customers.models import Customer
from apps.customers.services import register_credit_payment
from apps.inventory.models import InventoryMovement, Stock
from apps.inventory.services import create_initial_stock
from apps.products.models import Product
from apps.purchases.models import Purchase, PurchaseItem
from apps.purchases.services import confirm_purchase
from apps.reports.selectors import DATE_BASIS_BUSINESS, DATE_BASIS_REAL, get_report_summary
from apps.sales.models import Sale
from apps.sales.services import add_sale_item, confirm_sale, create_sale
from apps.settings_app.models import BusinessDateChange, BusinessDateSettings
from apps.settings_app.services import change_business_date
from apps.transfers.models import Transfer, TransferItem
from apps.transfers.services import receive_transfer, send_transfer
from apps.users.models import User


class HistoricalWorkflowTests(TestCase):
	def setUp(self):
		self.central = Branch.objects.create(name="Central", code="CENTRAL")
		self.north = Branch.objects.create(name="Norte", code="NORTE")
		self.admin = User.objects.create_user(username="admin-central", role=User.ROLE_ADMIN, branch=self.central)
		self.cashier = User.objects.create_user(username="cajero-norte", role=User.ROLE_CAJERO, branch=self.north)
		self.warehouse = User.objects.create_user(username="almacen-norte", role=User.ROLE_ALMACENERO, branch=self.north)
		self.superadmin = User.objects.create_user(username="super", role=User.ROLE_SUPERADMIN)
		self.product = Product.objects.create(name="Producto", sku="PRODUCTO", cost_price=5, list_price=10)
		self.customer = Customer.objects.create(first_name="Ana", last_name="Pérez", id_document="123", created_by=self.admin)
		self.day1 = timezone.localdate() - timedelta(days=4)
		self.day2 = self.day1 + timedelta(days=1)

	def change_day(self, day):
		change_business_date(user=self.admin, mode=BusinessDateSettings.MODE_HISTORICAL, business_date=day)

	def purchase(self, day, quantity):
		purchase = Purchase.objects.create(branch=self.central, purchase_date=day, created_by=self.admin)
		PurchaseItem.objects.create(purchase=purchase, product=self.product, quantity=quantity, unit_cost=5, sale_price=10)
		confirm_purchase(purchase=purchase, user=self.admin)
		purchase.refresh_from_db()
		return purchase

	def draft_sale(self, user, quantity):
		sale = create_sale(user=user)
		add_sale_item(sale=sale, product=self.product, quantity=quantity, user=user)
		return sale

	def report(self, day, basis=DATE_BASIS_BUSINESS, branch=None):
		return get_report_summary(user=self.superadmin, branch=branch, start_date=day, end_date=day, date_basis=basis)

	@patch("apps.settings_app.services.HISTORICAL_OPERATIONS_SUPPORTED", True)
	def test_two_days_two_branches_and_return_to_automatic(self):
		before = timezone.now()
		self.change_day(self.day1)
		create_initial_stock(product=self.product, branch=self.central, quantity=5, user=self.admin)
		first_purchase = self.purchase(self.day1, 3)
		transfer = Transfer.objects.create(origin_branch=self.central, destination_branch=self.north, created_by=self.admin)
		TransferItem.objects.create(transfer=transfer, product=self.product, requested_quantity=3)
		send_transfer(transfer, self.admin)
		with self.assertRaisesMessage(ValidationError, "Recibe los traspasos pendientes"):
			self.change_day(self.day2)
		self.assertFalse(Stock.objects.filter(product=self.product, branch=self.north).exists())
		receive_transfer(transfer, self.warehouse, {})
		transfer.refresh_from_db()
		self.assertEqual(transfer.business_date, self.day1)
		self.assertEqual(transfer.outgoing_movement.movement_date, self.day1)
		self.assertEqual(transfer.incoming_movement.movement_date, self.day1)

		central_register = open_cash_register(user=self.admin, opening_amount=Decimal("100"))
		north_register = open_cash_register(user=self.cashier, opening_amount=Decimal("100"))
		with self.assertRaisesMessage(ValidationError, "Cierra todas las cajas"):
			self.change_day(self.day2)
		central_sale = self.draft_sale(self.admin, 2)
		confirm_sale(sale=central_sale, user=self.admin, payment_method=Sale.PAYMENT_QR)
		north_sale = self.draft_sale(self.cashier, 4)
		movements_before = InventoryMovement.objects.count()
		with self.assertRaisesMessage(ValidationError, "Existencia insuficiente"):
			confirm_sale(sale=north_sale, user=self.cashier, payment_method=Sale.PAYMENT_QR)
		north_sale.refresh_from_db()
		self.assertEqual(north_sale.status, Sale.STATUS_DRAFT)
		self.assertIsNone(north_sale.business_date)
		self.assertEqual(Stock.objects.get(product=self.product, branch=self.north).quantity, 3)
		self.assertEqual(InventoryMovement.objects.count(), movements_before)
		self.assertFalse(CashMovement.objects.filter(cash_register=north_register, movement_type=CashMovement.TYPE_SALE).exists())
		item = north_sale.items.get()
		item.quantity = 2
		item.save()
		confirm_sale(sale=north_sale, user=self.cashier, payment_method=Sale.PAYMENT_QR)
		close_cash_register(cash_register=central_register, user=self.admin, closing_amount=Decimal("120"))
		close_cash_register(cash_register=north_register, user=self.cashier, closing_amount=Decimal("120"))
		self.assertEqual(Stock.objects.get(product=self.product, branch=self.central).quantity, 3)
		self.assertEqual(Stock.objects.get(product=self.product, branch=self.north).quantity, 1)

		self.change_day(self.day2)
		second_purchase = self.purchase(self.day2, 2)
		central_register2 = open_cash_register(user=self.admin, opening_amount=Decimal("100"))
		north_register2 = open_cash_register(user=self.cashier, opening_amount=Decimal("100"))
		sale2 = self.draft_sale(self.admin, 1)
		confirm_sale(sale=sale2, user=self.admin, payment_method=Sale.PAYMENT_CASH, cash_received=Decimal("10"))
		credit_sale = self.draft_sale(self.cashier, 1)
		confirm_sale(sale=credit_sale, user=self.cashier, payment_method=Sale.PAYMENT_CREDIT, customer=self.customer)
		credit_sale.refresh_from_db()
		payment = register_credit_payment(credit_pk=credit_sale.credit.pk, amount=Decimal("10"), user=self.cashier)
		close_cash_register(cash_register=central_register2, user=self.admin, closing_amount=Decimal("110"))
		close_cash_register(cash_register=north_register2, user=self.cashier, closing_amount=Decimal("110"))
		self.assertEqual(Stock.objects.get(product=self.product, branch=self.central).quantity, 4)
		self.assertEqual(Stock.objects.get(product=self.product, branch=self.north).quantity, 0)
		credit_sale.credit.refresh_from_db()
		self.assertEqual(credit_sale.credit.balance, Decimal("0"))
		self.assertEqual(payment.business_date, self.day2)
		for register, day in ((central_register, self.day1), (north_register, self.day1), (central_register2, self.day2), (north_register2, self.day2)):
			register.refresh_from_db()
			self.assertEqual((register.status, register.business_date, register.difference), (CashRegister.STATUS_CLOSED, day, Decimal("0")))
			self.assertGreaterEqual(register.opened_at, before)
			self.assertGreaterEqual(register.closed_at, before)
		for sale, day in ((central_sale, self.day1), (north_sale, self.day1), (sale2, self.day2), (credit_sale, self.day2)):
			sale.refresh_from_db()
			self.assertEqual(sale.business_date, day)
			self.assertEqual(sale.inventory_movement.movement_date, day)
			self.assertGreaterEqual(sale.confirmed_at, before)
		for purchase, day in ((first_purchase, self.day1), (second_purchase, self.day2)):
			self.assertEqual(purchase.business_date, day)
			self.assertEqual(purchase.inventory_movement.movement_date, day)
			self.assertGreaterEqual(purchase.confirmed_at, before)

		first_report, second_report = self.report(self.day1), self.report(self.day2)
		self.assertEqual((first_report["sales_count"], first_report["sales_total"], first_report["purchases_total"], first_report["closed_cash_registers"]), (2, Decimal("40"), Decimal("15"), 2))
		self.assertEqual((second_report["sales_count"], second_report["sales_total"], second_report["purchases_total"], second_report["closed_cash_registers"]), (2, Decimal("20"), Decimal("10"), 2))
		self.assertEqual((second_report["credit_issued"], second_report["credit_collected"], second_report["credit_balance"]), (Decimal("10"), Decimal("10"), Decimal("0")))
		self.assertEqual(self.report(self.day1, branch=self.north)["sales_total"], Decimal("20"))
		self.assertEqual(self.report(self.day2, branch=self.north)["purchases_count"], 0)
		self.assertEqual(self.report(self.day1, basis=DATE_BASIS_REAL)["sales_count"], 0)
		self.assertEqual(self.report(timezone.localdate(), basis=DATE_BASIS_REAL)["sales_count"], 4)
		self.client.force_login(self.admin)
		response = self.client.get(reverse("reports:index"))
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.context["date_basis"], DATE_BASIS_BUSINESS)
		self.assertEqual(response.context["report"]["sales_total"], Decimal("10"))
		self.assertContains(response, f'value="{self.day2.isoformat()}"')
		change_business_date(user=self.admin, mode=BusinessDateSettings.MODE_AUTOMATIC)
		self.assertEqual(BusinessDateSettings.objects.get(pk=1).mode, BusinessDateSettings.MODE_AUTOMATIC)
		self.assertEqual(BusinessDateChange.objects.count(), 3)

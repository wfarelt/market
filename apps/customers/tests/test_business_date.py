from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.branches.models import Branch
from apps.cash.models import CashMovement, CashRegister
from apps.cash.services import close_cash_register, open_cash_register
from apps.customers.models import Credit, CreditPayment, Customer
from apps.customers.services import register_credit_payment
from apps.inventory.models import Stock
from apps.products.models import Product
from apps.sales.models import Sale
from apps.sales.services import add_sale_item, confirm_sale, create_sale
from apps.settings_app.models import BusinessDateSettings
from apps.users.models import User


class CreditBusinessDateTests(TestCase):
	def setUp(self):
		self.branch = Branch.objects.create(name="Central", code="CENTRAL")
		self.user = User.objects.create_user(username="cajero", role=User.ROLE_CAJERO, branch=self.branch)
		self.past = timezone.localdate() - timedelta(days=4)
		BusinessDateSettings.objects.filter(pk=1).update(mode=BusinessDateSettings.MODE_HISTORICAL, business_date=self.past)
		self.register = open_cash_register(user=self.user, opening_amount=Decimal("10.00"))
		self.customer = Customer.objects.create(first_name="Ana", last_name="Pérez", id_document="123", created_by=self.user)
		self.product = Product.objects.create(name="Producto", sku="PROD", list_price=Decimal("20.00"))
		Stock.objects.create(product=self.product, branch=self.branch, quantity=2)
		sale = create_sale(user=self.user)
		add_sale_item(sale=sale, product=self.product, quantity=1, user=self.user)
		confirm_sale(sale=sale, user=self.user, payment_method=Sale.PAYMENT_CREDIT, customer=self.customer)
		self.credit = sale.credit
		self.client.force_login(self.user)

	def test_historical_payment_preserves_real_date_and_updates_cash_and_balance(self):
		before = timezone.now()
		payment = register_credit_payment(credit_pk=self.credit.pk, amount=Decimal("5.00"), user=self.user)
		after = timezone.now()
		self.credit.refresh_from_db()
		self.assertEqual(self.credit.sale.business_date, self.past)
		self.assertEqual(payment.business_date, self.past)
		self.assertLessEqual(before, payment.created_at)
		self.assertLessEqual(payment.created_at, after)
		self.assertEqual(self.credit.balance, Decimal("15.00"))
		self.assertEqual(self.credit.status, Credit.STATUS_PARTIAL)
		self.assertEqual(payment.cash_movement.amount, Decimal("5.00"))
		self.register.refresh_from_db()
		self.assertEqual(self.register.total_credit_collections, Decimal("5.00"))
		for url in (
			reverse("customers:credit-detail", args=[self.credit.pk]),
			reverse("customers:account-statement", args=[self.customer.pk]),
		):
			response = self.client.get(url)
			self.assertContains(response, self.past.strftime("%d/%m/%Y"))
			self.assertContains(response, "Registro real")
			self.assertContains(response, timezone.localtime(payment.created_at).strftime("%d/%m/%Y %H:%M"))

	def test_mismatched_or_missing_cash_date_rejects_payment_without_changes(self):
		for business_date in (None, self.past - timedelta(days=1)):
			with self.subTest(business_date=business_date):
				CashRegister.objects.filter(pk=self.register.pk).update(business_date=business_date)
				with self.assertRaisesMessage(ValidationError, "La fecha de negocio de la caja no coincide"):
					register_credit_payment(credit_pk=self.credit.pk, amount=Decimal("5.00"), user=self.user)
				self.credit.refresh_from_db()
				self.assertEqual(self.credit.balance, Decimal("20.00"))
				self.assertFalse(CreditPayment.objects.exists())
				self.assertFalse(CashMovement.objects.filter(movement_type=CashMovement.TYPE_CREDIT_COLLECTION).exists())
		response = self.client.post(reverse("customers:credit-payment", args=[self.credit.pk]), {"amount": "5.00"})
		self.assertContains(response, "La fecha de negocio de la caja no coincide")

	def test_automatic_payment_uses_register_date_and_accepts_legacy_register(self):
		BusinessDateSettings.objects.filter(pk=1).update(mode=BusinessDateSettings.MODE_AUTOMATIC, business_date=None)
		CashRegister.objects.filter(pk=self.register.pk).update(business_date=None)
		payment = register_credit_payment(credit_pk=self.credit.pk, amount=Decimal("5.00"), user=self.user)
		self.assertIsNone(payment.business_date)
		response = self.client.get(reverse("customers:credit-detail", args=[self.credit.pk]))
		self.assertContains(response, "No determinada")

	def test_historical_payment_respects_payment_amount_validation(self):
		with self.assertRaises(ValidationError):
			register_credit_payment(credit_pk=self.credit.pk, amount=Decimal("25.00"), user=self.user)
		self.assertFalse(CreditPayment.objects.exists())
		self.assertFalse(CashMovement.objects.filter(movement_type=CashMovement.TYPE_CREDIT_COLLECTION).exists())

	def test_payments_on_different_working_days_keep_their_own_dates(self):
		first = register_credit_payment(credit_pk=self.credit.pk, amount=Decimal("5.00"), user=self.user)
		close_cash_register(cash_register=self.register, user=self.user, closing_amount=Decimal("15.00"))
		next_date = self.past + timedelta(days=1)
		BusinessDateSettings.objects.filter(pk=1).update(business_date=next_date)
		open_cash_register(user=self.user, opening_amount=Decimal("10.00"))
		second = register_credit_payment(credit_pk=self.credit.pk, amount=Decimal("15.00"), user=self.user)
		self.credit.refresh_from_db()
		self.assertEqual(first.business_date, self.past)
		self.assertEqual(second.business_date, next_date)
		self.assertEqual(self.credit.balance, Decimal("0.00"))
		self.assertEqual(self.credit.status, Credit.STATUS_PAID)

	def test_historical_payment_rejects_credit_from_another_branch(self):
		other_branch = Branch.objects.create(name="Norte", code="NORTE")
		other_user = User.objects.create_user(username="norte", role=User.ROLE_CAJERO, branch=other_branch)
		open_cash_register(user=other_user, opening_amount=0)
		with self.assertRaisesMessage(ValidationError, "El crédito y la caja deben pertenecer a la misma sucursal."):
			register_credit_payment(credit_pk=self.credit.pk, amount=Decimal("5.00"), user=other_user)
		self.credit.refresh_from_db()
		self.assertEqual(self.credit.balance, Decimal("20.00"))
		self.assertFalse(CreditPayment.objects.exists())

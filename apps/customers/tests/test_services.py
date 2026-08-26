from decimal import Decimal
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from apps.branches.models import Branch
from apps.cash.models import CashMovement, CashRegister
from apps.customers.models import Credit, CreditPayment, Customer
from apps.customers.services import (
	create_customer,
	register_credit_payment,
	update_customer,
)
from apps.inventory.models import Stock
from apps.products.models import Product
from apps.sales.models import Sale
from apps.sales.services import add_sale_item, confirm_sale, create_sale
from apps.users.models import User


class CustomersModuleTests(TestCase):
	def setUp(self):
		self.branch = Branch.objects.create(name="Central", code="CENTRAL")
		self.admin_user = User.objects.create_user(
			username="admin", password="password", branch=self.branch, role=User.ROLE_ADMIN
		)
		self.cajero_user = User.objects.create_user(
			username="cajero", password="password", branch=self.branch, role=User.ROLE_CAJERO
		)
		self.cash_register = CashRegister.objects.create(
			user=self.cajero_user,
			branch=self.branch,
			opening_amount=Decimal("100.00"),
			status=CashRegister.STATUS_OPEN,
		)
		self.product = Product.objects.create(
			name="Producto Prueba",
			sku="PROD001",
			list_price=Decimal("100.00"),
			is_active=True,
		)
		Stock.objects.create(
			branch=self.branch,
			product=self.product,
			quantity=Decimal("10.00"),
		)

	def test_create_customer(self):
		customer = create_customer(
			first_name="Juan",
			last_name="Pérez",
			id_document="1234567",
			phone="70000000",
			user=self.admin_user,
		)
		self.assertEqual(customer.full_name, "Juan Pérez")
		self.assertTrue(customer.code.startswith("CLI-"))

	def test_prevent_duplicate_id_document(self):
		create_customer(
			first_name="Juan",
			last_name="Pérez",
			id_document="1234567",
			user=self.admin_user,
		)
		with self.assertRaises(ValidationError):
			create_customer(
				first_name="Maria",
				last_name="Gomez",
				id_document="1234567",
				user=self.admin_user,
			)

	def test_create_credit_from_sale(self):
		customer = create_customer(
			first_name="Juan",
			last_name="Pérez",
			id_document="1234567",
			user=self.admin_user,
		)
		sale = create_sale(user=self.cajero_user)
		add_sale_item(sale=sale, product=self.product, quantity=2, user=self.cajero_user)
		confirm_sale(
			sale=sale,
			user=self.cajero_user,
			payment_method=Sale.PAYMENT_CREDIT,
			customer=customer,
		)

		sale.refresh_from_db()
		self.assertEqual(sale.status, Sale.STATUS_COMPLETED)
		self.assertIsNotNone(sale.credit)
		self.assertEqual(sale.credit.original_amount, Decimal("200.00"))
		self.assertEqual(sale.credit.balance, Decimal("200.00"))
		self.assertEqual(sale.credit.status, Credit.STATUS_PENDING)

	def test_register_partial_and_total_credit_payment(self):
		customer = create_customer(
			first_name="Juan",
			last_name="Pérez",
			id_document="1234567",
			user=self.admin_user,
		)
		sale = create_sale(user=self.cajero_user)
		add_sale_item(sale=sale, product=self.product, quantity=2, user=self.cajero_user)
		confirm_sale(
			sale=sale,
			user=self.cajero_user,
			payment_method=Sale.PAYMENT_CREDIT,
			customer=customer,
		)
		credit = sale.credit

		# Pago parcial
		payment1 = register_credit_payment(
			credit_pk=credit.pk,
			amount=Decimal("50.00"),
			user=self.cajero_user,
			notes="Primer pago",
		)
		credit.refresh_from_db()
		self.assertEqual(credit.balance, Decimal("150.00"))
		self.assertEqual(credit.status, Credit.STATUS_PARTIAL)
		self.assertEqual(payment1.cash_movement.amount, Decimal("50.00"))
		self.assertEqual(payment1.cash_movement.movement_type, CashMovement.TYPE_CREDIT_COLLECTION)

		# Pago total restante
		register_credit_payment(
			credit_pk=credit.pk,
			amount=Decimal("150.00"),
			user=self.cajero_user,
			notes="Pago final",
		)
		credit.refresh_from_db()
		self.assertEqual(credit.balance, Decimal("0.00"))
		self.assertEqual(credit.status, Credit.STATUS_PAID)

	def test_prevent_overpayment(self):
		customer = create_customer(
			first_name="Juan",
			last_name="Pérez",
			id_document="1234567",
			user=self.admin_user,
		)
		sale = create_sale(user=self.cajero_user)
		add_sale_item(sale=sale, product=self.product, quantity=1, user=self.cajero_user)
		confirm_sale(
			sale=sale,
			user=self.cajero_user,
			payment_method=Sale.PAYMENT_CREDIT,
			customer=customer,
		)

		with self.assertRaises(ValidationError):
			register_credit_payment(
				credit_pk=sale.credit.pk,
				amount=Decimal("150.00"),
				user=self.cajero_user,
			)

	def test_payment_requires_open_cash_register(self):
		customer = create_customer(
			first_name="Juan",
			last_name="Pérez",
			id_document="1234567",
			user=self.admin_user,
		)
		sale = create_sale(user=self.cajero_user)
		add_sale_item(sale=sale, product=self.product, quantity=1, user=self.cajero_user)
		confirm_sale(
			sale=sale,
			user=self.cajero_user,
			payment_method=Sale.PAYMENT_CREDIT,
			customer=customer,
		)

		user_without_cash = User.objects.create_user(
			username="cajero2", password="password", branch=self.branch, role=User.ROLE_CAJERO
		)
		with self.assertRaises(ValidationError):
			register_credit_payment(
				credit_pk=sale.credit.pk,
				amount=Decimal("50.00"),
				user=user_without_cash,
			)

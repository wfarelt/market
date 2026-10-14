from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from apps.branches.models import Branch
from apps.cash.models import CashRegister
from apps.customers.models import Customer
from apps.users.models import User


class CustomerCreationViewTests(TestCase):
	def setUp(self):
		self.branch = Branch.objects.create(name="Central", code="CENTRAL")
		self.cashier = User.objects.create_user(
			username="cashier-customer",
			password="test-password",
			branch=self.branch,
			role=User.ROLE_CAJERO,
		)
		CashRegister.objects.create(
			user=self.cashier,
			branch=self.branch,
			opening_amount=Decimal("100.00"),
			status=CashRegister.STATUS_OPEN,
		)
		self.client.force_login(self.cashier)

	def customer_data(self, **overrides):
		data = {
			"first_name": "Ana",
			"last_name": "Pérez",
			"id_document": "12345678",
			"tax_id": "",
			"phone": "70000000",
			"address": "",
			"email": "",
		}
		data.update(overrides)
		return data

	def test_cashier_can_create_customer_from_customer_module(self):
		response = self.client.get(reverse("customers:list"))
		self.assertContains(response, reverse("customers:create"))

		response = self.client.get(reverse("customers:create"))
		self.assertEqual(response.status_code, 200)
		self.assertNotContains(response, 'name="is_active"')

		response = self.client.post(reverse("customers:create"), self.customer_data())

		customer = Customer.objects.get(id_document="12345678")
		self.assertRedirects(response, reverse("customers:list"))
		self.assertEqual(customer.created_by, self.cashier)
		self.assertTrue(customer.is_active)

	def test_cashier_can_create_customer_from_pos_and_customer_is_preselected(self):
		response = self.client.post(
			reverse("customers:create") + "?source=pos",
			self.customer_data(source="pos"),
		)

		customer = Customer.objects.get(id_document="12345678")
		self.assertRedirects(response, f"{reverse('sales:pos')}?customer={customer.pk}")

		response = self.client.get(reverse("sales:pos"), {"customer": customer.pk})
		self.assertEqual(response.status_code, 200)
		self.assertEqual(str(response.context["checkout_form"].initial["customer"]), str(customer.pk))
		self.assertContains(response, f'value="{customer.pk}" selected')

	def test_cashier_still_cannot_edit_customer(self):
		customer = Customer.objects.create(
			first_name="Ana",
			last_name="Pérez",
			id_document="87654321",
			created_by=self.cashier,
		)

		response = self.client.get(reverse("customers:update", args=[customer.pk]))

		self.assertEqual(response.status_code, 403)


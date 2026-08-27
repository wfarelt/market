from decimal import Decimal
from django.test import TestCase
from django.urls import reverse

from apps.branches.models import Branch
from apps.cash.models import CashRegister
from apps.users.models import User


class CashViewTests(TestCase):
	def setUp(self):
		self.branch = Branch.objects.create(name="Central", code="CENTRAL")
		self.cajero = User.objects.create_user(
			username="cajero",
			password="test-password",
			branch=self.branch,
			role=User.ROLE_CAJERO,
		)
		self.client.force_login(self.cajero)

	def test_close_cash_register_view_renders_details(self):
		register = CashRegister.objects.create(
			user=self.cajero,
			branch=self.branch,
			opening_amount=Decimal("150.00"),
			status=CashRegister.STATUS_OPEN,
		)
		url = reverse("cash:close", kwargs={"pk": register.pk})
		response = self.client.get(url)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Resumen de la Sesión de Caja")
		self.assertContains(response, "150.00")

	def test_open_cash_register_prefills_remaining_petty_cash(self):
		from apps.cash.models import ExpenseCategory
		from apps.cash.services import close_cash_register, register_petty_cash_expense
		category = ExpenseCategory.objects.create(name="Gastos varios")
		first_reg = CashRegister.objects.create(
			user=self.cajero,
			branch=self.branch,
			opening_amount=Decimal("100.00"),
			status=CashRegister.STATUS_OPEN,
		)
		register_petty_cash_expense(
			cash_register=first_reg,
			category=category,
			concept="Taxi",
			amount=Decimal("30.00"),
			user=self.cajero,
		)
		close_cash_register(cash_register=first_reg, user=self.cajero, closing_amount=Decimal("70.00"))

		response = self.client.get(reverse("cash:open"))
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'value="70.00"')
		self.assertContains(response, "Remanente de Caja Chica Anterior")


from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from apps.branches.models import Branch
from apps.cash.models import CashMovement, CashRegister, ExpenseCategory
from apps.cash.services import close_cash_register, open_cash_register, register_petty_cash_expense
from apps.users.models import User


class CashRegisterServiceTests(TestCase):
	def setUp(self):
		self.branch = Branch.objects.create(name="Central", code="CENTRAL")
		self.user = User.objects.create_user(username="cashier", password="test-password", branch=self.branch, role=User.ROLE_CAJERO)
		self.category = ExpenseCategory.objects.create(name="Transporte")

	def test_user_cannot_open_two_cash_registers(self):
		open_cash_register(user=self.user, opening_amount=Decimal("100"))

		with self.assertRaises(ValidationError):
			open_cash_register(user=self.user, opening_amount=Decimal("50"))

	def test_opening_and_closing_create_movements(self):
		cash_register = open_cash_register(user=self.user, opening_amount=Decimal("100"))
		register_petty_cash_expense(cash_register=cash_register, category=self.category, concept="Taxi", amount=Decimal("20"), user=self.user)
		close_cash_register(cash_register=cash_register, user=self.user, closing_amount=Decimal("150"))

		cash_register.refresh_from_db()
		self.assertEqual(cash_register.status, CashRegister.STATUS_CLOSED)
		self.assertEqual(cash_register.expected_amount, Decimal("80"))
		self.assertEqual(cash_register.difference, Decimal("70"))
		self.assertEqual(
			list(cash_register.movements.values_list("movement_type", flat=True)),
			[CashMovement.TYPE_CLOSING, CashMovement.TYPE_PETTY_CASH_EXPENSE, CashMovement.TYPE_OPENING],
		)

	def test_petty_cash_expenses_cannot_exceed_opening_amount(self):
		cash_register = open_cash_register(user=self.user, opening_amount=Decimal("100.00"))
		register_petty_cash_expense(
			cash_register=cash_register,
			category=self.category,
			concept="Taxi 1",
			amount=Decimal("60.00"),
			user=self.user,
		)
		self.assertEqual(cash_register.remaining_petty_cash, Decimal("40.00"))

		with self.assertRaises(ValidationError):
			register_petty_cash_expense(
				cash_register=cash_register,
				category=self.category,
				concept="Taxi 2",
				amount=Decimal("50.00"),
				user=self.user,
			)

	def test_cashier_can_open_cash_from_the_web_flow(self):
		self.client.force_login(self.user)

		response = self.client.post(
			reverse("cash:open"),
			{"opening_amount": "100.00", "notes": ""},
		)

		self.assertRedirects(response, reverse("cash:list"))
		self.assertTrue(CashRegister.objects.filter(user=self.user, status=CashRegister.STATUS_OPEN).exists())


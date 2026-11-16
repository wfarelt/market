from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from apps.branches.models import Branch
from apps.cash.models import CashClosureCorrection, CashMovement, CashRegister, ExpenseCategory, PettyCashExpense
from apps.cash.services import close_cash_register, correct_cash_closing, open_cash_register, register_petty_cash_expense
from apps.users.models import User


class CashAdminReadOnlyTests(TestCase):
	def setUp(self):
		self.branch = Branch.objects.create(name="Central", code="CENTRAL")
		self.operator = User.objects.create_user(username="cajero", role=User.ROLE_CAJERO, branch=self.branch)
		self.admin = User.objects.create_superuser(username="admin", password="test-password")
		self.client.force_login(self.admin)
		self.register = open_cash_register(user=self.operator, opening_amount=Decimal("100.00"))
		self.category = ExpenseCategory.objects.create(name="Otros")
		self.expense = register_petty_cash_expense(
			cash_register=self.register, category=self.category, concept="Transporte",
			amount=Decimal("10.00"), user=self.operator,
		)
		close_cash_register(cash_register=self.register, user=self.operator, closing_amount=Decimal("90.00"))
		self.register.refresh_from_db()
		correct_cash_closing(cash_register=self.register, user=self.admin, closing_amount=Decimal("91.00"), reason="Corrección")
		self.register.refresh_from_db()
		self.correction = CashClosureCorrection.objects.get(cash_register=self.register)

	def test_registers_expenses_and_corrections_allow_view_but_not_write(self):
		for model, obj in (
			("cashregister", self.register),
			("pettycashexpense", self.expense),
			("cashclosurecorrection", self.correction),
		):
			with self.subTest(model=model):
				change_url = reverse(f"admin:cash_{model}_change", args=[obj.pk])
				self.assertEqual(self.client.get(change_url).status_code, 200)
				self.assertEqual(self.client.post(change_url, {"_save": "Save"}).status_code, 403)
				self.assertEqual(self.client.get(reverse(f"admin:cash_{model}_add")).status_code, 403)
				self.assertEqual(self.client.post(reverse(f"admin:cash_{model}_add"), {}).status_code, 403)
				delete_url = reverse(f"admin:cash_{model}_delete", args=[obj.pk])
				self.assertEqual(self.client.get(delete_url).status_code, 403)
				self.assertEqual(self.client.post(delete_url, {"post": "yes"}).status_code, 403)
		self.register.refresh_from_db()
		self.expense.refresh_from_db()
		self.assertEqual(self.register.closing_amount, Decimal("91.00"))
		self.assertEqual(self.expense.amount, Decimal("10.00"))
		self.assertEqual(CashMovement.objects.filter(cash_register=self.register).count(), 3)

	def test_movements_are_visible_without_inline_add_or_change(self):
		response = self.client.get(reverse("admin:cash_cashregister_change", args=[self.register.pk]))
		self.assertContains(response, "Transporte")
		self.assertNotContains(response, 'name="movements-0-amount"')
		self.assertNotContains(response, "Añadir otro")

	def test_bulk_delete_action_cannot_delete_cash_registers(self):
		response = self.client.post(reverse("admin:cash_cashregister_changelist"), {
			"action": "delete_selected", "_selected_action": [self.register.pk], "post": "yes",
		})
		self.assertEqual(response.status_code, 200)
		self.assertTrue(CashRegister.objects.filter(pk=self.register.pk).exists())
		self.assertTrue(CashMovement.objects.filter(cash_register=self.register).exists())

	def test_expense_categories_remain_editable(self):
		change_url = reverse("admin:cash_expensecategory_change", args=[self.category.pk])
		response = self.client.post(change_url, {"name": "Servicios", "is_active": "on", "_save": "Save"})
		self.assertEqual(response.status_code, 302)
		self.category.refresh_from_db()
		self.assertEqual(self.category.name, "Servicios")

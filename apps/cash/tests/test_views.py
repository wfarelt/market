from decimal import Decimal
from django.test import TestCase
from django.urls import reverse

from apps.branches.models import Branch
from apps.cash.models import CashClosureCorrection, CashMovement, CashRegister
from apps.cash.services import close_cash_register, open_cash_register
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

	def test_admin_can_filter_registers_by_any_branch_and_user(self):
		other_branch = Branch.objects.create(name="Norte", code="NORTE")
		other_cashier = User.objects.create_user(
			username="cajero-norte",
			password="test-password",
			branch=other_branch,
			role=User.ROLE_CAJERO,
		)
		own_register = CashRegister.objects.create(user=self.cajero, branch=self.branch, opening_amount=Decimal("100.00"))
		other_register = CashRegister.objects.create(user=other_cashier, branch=other_branch, opening_amount=Decimal("150.00"))
		admin = User.objects.create_user(
			username="admin",
			password="test-password",
			branch=self.branch,
			role=User.ROLE_ADMIN,
		)
		self.client.force_login(admin)

		response = self.client.get(reverse("cash:list"))
		self.assertEqual(response.status_code, 200)
		self.assertEqual(set(response.context["cash_registers"].values_list("pk", flat=True)), {own_register.pk, other_register.pk})
		self.assertContains(response, 'name="branch"')
		self.assertContains(response, 'name="user"')

		response = self.client.get(reverse("cash:list"), {"branch": other_branch.pk})
		self.assertEqual(list(response.context["cash_registers"].values_list("pk", flat=True)), [other_register.pk])
		self.assertContains(response, f'value="{other_branch.pk}" selected')

		response = self.client.get(reverse("cash:list"), {"user": other_cashier.pk})
		self.assertEqual(list(response.context["cash_registers"].values_list("pk", flat=True)), [other_register.pk])

		response = self.client.get(reverse("cash:list"), {"branch": self.branch.pk, "user": other_cashier.pk})
		self.assertEqual(list(response.context["cash_registers"]), [])

		response = self.client.get(reverse("cash:list"), {"branch": "9" * 20})
		self.assertEqual(list(response.context["cash_registers"]), [])

	def test_non_admin_cannot_expand_register_list_with_filters(self):
		other_branch = Branch.objects.create(name="Norte", code="NORTE")
		other_cashier = User.objects.create_user(
			username="cajero-norte",
			password="test-password",
			branch=other_branch,
			role=User.ROLE_CAJERO,
		)
		own_register = CashRegister.objects.create(user=self.cajero, branch=self.branch, opening_amount=Decimal("100.00"))
		CashRegister.objects.create(user=other_cashier, branch=other_branch, opening_amount=Decimal("150.00"))

		response = self.client.get(reverse("cash:list"), {"branch": other_branch.pk, "user": other_cashier.pk})

		self.assertEqual(list(response.context["cash_registers"].values_list("pk", flat=True)), [own_register.pk])
		self.assertNotContains(response, 'name="branch"')
		self.assertNotContains(response, 'name="user"')

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

	def test_cashier_cannot_access_closing_correction(self):
		register = CashRegister.objects.create(
			user=self.cajero,
			branch=self.branch,
			opening_amount=Decimal("150.00"),
			status=CashRegister.STATUS_CLOSED,
			closing_amount=Decimal("120.00"),
			expected_amount=Decimal("100.00"),
			difference=Decimal("20.00"),
		)

		response = self.client.get(reverse("cash:correct-closing", kwargs={"pk": register.pk}))

		self.assertEqual(response.status_code, 404)

	def test_branch_admin_corrects_counted_amount_and_detail_shows_audit_history(self):
		admin = User.objects.create_user(
			username="admin",
			password="test-password",
			branch=self.branch,
			role=User.ROLE_ADMIN,
		)
		cashier = User.objects.create_user(
			username="cashier-2",
			password="test-password",
			branch=self.branch,
			role=User.ROLE_CAJERO,
		)
		register = open_cash_register(user=cashier, opening_amount=Decimal("100.00"))
		close_cash_register(cash_register=register, user=cashier, closing_amount=Decimal("150.00"))
		self.client.force_login(admin)
		form_response = self.client.get(reverse("cash:correct-closing", kwargs={"pk": register.pk}))
		self.assertEqual(form_response.status_code, 200)
		self.assertContains(form_response, "Monto contado vigente")

		response = self.client.post(
			reverse("cash:correct-closing", kwargs={"pk": register.pk}),
			{"closing_amount": "130.00", "reason": "Error de digitación."},
		)

		self.assertRedirects(response, reverse("cash:detail", kwargs={"pk": register.pk}))
		register.refresh_from_db()
		self.assertEqual(register.closing_amount, Decimal("130.00"))
		self.assertEqual(register.difference, Decimal("30.00"))
		self.assertEqual(register.movements.get(movement_type=CashMovement.TYPE_CLOSING).amount, Decimal("150.00"))
		self.assertEqual(CashClosureCorrection.objects.get(cash_register=register).created_by, admin)

		response = self.client.get(reverse("cash:detail", kwargs={"pk": register.pk}))
		self.assertContains(response, "Historial de rectificaciones del monto contado")
		self.assertContains(response, "Error de digitación.")

	def test_branch_admin_cannot_correct_register_from_another_branch(self):
		other_branch = Branch.objects.create(name="Norte", code="NORTE")
		register = CashRegister.objects.create(
			user=self.cajero,
			branch=other_branch,
			status=CashRegister.STATUS_CLOSED,
			opening_amount=Decimal("100.00"),
			closing_amount=Decimal("120.00"),
			expected_amount=Decimal("100.00"),
			difference=Decimal("20.00"),
		)
		admin = User.objects.create_user(
			username="admin",
			password="test-password",
			branch=self.branch,
			role=User.ROLE_ADMIN,
		)
		self.client.force_login(admin)

		response = self.client.get(reverse("cash:correct-closing", kwargs={"pk": register.pk}))

		self.assertEqual(response.status_code, 404)


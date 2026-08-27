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


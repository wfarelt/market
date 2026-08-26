from django.test import TestCase
from django.urls import reverse

from apps.branches.models import Branch
from apps.users.models import User


class DashboardViewTests(TestCase):
	def test_dashboard_renders_branch_kpis_for_authenticated_user(self):
		branch = Branch.objects.create(name="Central", code="CENTRAL")
		user = User.objects.create_user(
			username="cashier",
			password="test-password",
			branch=branch,
			role=User.ROLE_CAJERO,
		)
		self.client.force_login(user)

		response = self.client.get(reverse("dashboard:index"))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Ventas de hoy")


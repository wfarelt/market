from django.test import TestCase
from django.urls import reverse

from apps.branches.models import Branch
from apps.users.models import User


class ReportDashboardViewTests(TestCase):
	def test_admin_can_view_branch_report_dashboard(self):
		branch = Branch.objects.create(name="Central", code="CENTRAL")
		user = User.objects.create_user(
			username="admin",
			password="test-password",
			branch=branch,
			role=User.ROLE_ADMIN,
		)
		self.client.force_login(user)

		response = self.client.get(reverse("reports:index"))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Reportes")
		self.assertContains(response, "Ventas")


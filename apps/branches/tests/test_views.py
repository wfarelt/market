from django.test import TestCase
from django.urls import reverse

from apps.branches.models import Branch
from apps.users.models import User


class BranchViewTests(TestCase):
	def setUp(self):
		self.branch = Branch.objects.create(name="Central", code="CENTRAL")
		self.admin_user = User.objects.create_user(
			username="admin",
			password="test-password",
			branch=self.branch,
			role=User.ROLE_ADMIN,
		)
		self.cajero_user = User.objects.create_user(
			username="cajero",
			password="test-password",
			branch=self.branch,
			role=User.ROLE_CAJERO,
		)

	def test_admin_can_access_branch_list(self):
		self.client.force_login(self.admin_user)
		response = self.client.get(reverse("branches:list"))
		self.assertEqual(response.status_code, 200)

	def test_cajero_forbidden_from_branch_list(self):
		self.client.force_login(self.cajero_user)
		response = self.client.get(reverse("branches:list"))
		self.assertEqual(response.status_code, 403)


from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from apps.branches.models import Branch
from apps.users.models import User


class UserModelTests(TestCase):
	def setUp(self):
		self.branch = Branch.objects.create(name="Central", code="CENTRAL")

	def test_operational_role_requires_branch(self):
		user = User(username="cashier", password="test-password", role=User.ROLE_CAJERO)

		with self.assertRaises(ValidationError):
			user.full_clean()

	def test_operational_role_accepts_branch(self):
		user = User(
			username="cashier",
			password="test-password",
			branch=self.branch,
			role=User.ROLE_CAJERO,
		)

		user.full_clean()

	def test_superadmin_cannot_have_branch(self):
		user = User(
			username="superadmin",
			password="test-password",
			branch=self.branch,
			role=User.ROLE_SUPERADMIN,
		)

		with self.assertRaises(ValidationError):
			user.full_clean()

	def test_admin_user_add_page_loads(self):
		admin_user = User.objects.create_superuser(
			username="admin",
			password="test-password",
		)
		self.client.force_login(admin_user)

		response = self.client.get(reverse("admin:users_user_add"))

		self.assertEqual(response.status_code, 200)

	def test_admin_can_manage_users_from_all_branches(self):
		second_branch = Branch.objects.create(name="Norte", code="NORTE")
		admin_user = User.objects.create_user(
			username="manager",
			password="test-password",
			branch=self.branch,
			role=User.ROLE_ADMIN,
		)
		cashier = User.objects.create_user(
			username="cashier-norte",
			password="test-password",
			branch=second_branch,
			role=User.ROLE_CAJERO,
		)
		self.client.force_login(admin_user)

		response = self.client.get(reverse("users:list"))

		self.assertContains(response, cashier.username)
		self.assertEqual(response.status_code, 200)

	def test_admin_cannot_edit_superadmin(self):
		admin_user = User.objects.create_user(
			username="manager",
			password="test-password",
			branch=self.branch,
			role=User.ROLE_ADMIN,
		)
		superadmin = User.objects.create_superuser(
			username="owner",
			password="test-password",
		)
		self.client.force_login(admin_user)

		response = self.client.get(reverse("users:update", args=[superadmin.pk]))

		self.assertEqual(response.status_code, 404)

	def test_logout_ends_the_user_session(self):
		user = User.objects.create_user(
			username="cashier",
			password="test-password",
			branch=self.branch,
			role=User.ROLE_CAJERO,
		)
		self.client.force_login(user)

		response = self.client.post(reverse("users:logout"))

		self.assertRedirects(response, reverse("users:login"))
		self.assertNotIn("_auth_user_id", self.client.session)


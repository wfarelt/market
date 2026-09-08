from django.test import TestCase
from django.urls import reverse

from apps.users.models import User


class ProfilePasswordChangeTests(TestCase):
	def test_authenticated_user_can_change_password(self):
		user = User.objects.create_user(username="user", password="old-password")
		self.client.force_login(user)

		response = self.client.post(reverse("users:profile"), {
			"old_password": "old-password",
			"new_password1": "new-password-123",
			"new_password2": "new-password-123",
		})

		user.refresh_from_db()
		self.assertRedirects(response, reverse("users:profile"))
		self.assertTrue(user.check_password("new-password-123"))


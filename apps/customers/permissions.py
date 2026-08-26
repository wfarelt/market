from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from apps.users.models import User


def can_manage_customers(user):
	return user.is_authenticated and user.role in {User.ROLE_SUPERADMIN, User.ROLE_ADMIN}


def can_access_customers_and_credits(user):
	return user.is_authenticated and user.role in {User.ROLE_SUPERADMIN, User.ROLE_ADMIN, User.ROLE_CAJERO}


class CustomerReadPaymentAccessMixin(LoginRequiredMixin, UserPassesTestMixin):
	def test_func(self):
		return can_access_customers_and_credits(self.request.user)


class CustomerManagementAccessMixin(LoginRequiredMixin, UserPassesTestMixin):
	def test_func(self):
		return can_manage_customers(self.request.user)

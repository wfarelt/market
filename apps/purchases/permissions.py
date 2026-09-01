from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

from apps.users.models import User


class PurchaseAccessMixin(LoginRequiredMixin, UserPassesTestMixin):
	def test_func(self):
		return self.request.user.role in {User.ROLE_SUPERADMIN, User.ROLE_ADMIN}

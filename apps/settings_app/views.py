from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.views.generic import UpdateView

from apps.users.models import User
from .forms import CompanySettingsForm
from .models import CompanySettings


class SettingsAccessMixin(LoginRequiredMixin, UserPassesTestMixin):
	def test_func(self):
		return self.request.user.role in {User.ROLE_SUPERADMIN, User.ROLE_ADMIN}


class CompanySettingsView(SettingsAccessMixin, UpdateView):
	model = CompanySettings
	form_class = CompanySettingsForm
	template_name = "settings_app/company_form.html"
	success_url = reverse_lazy("settings_app:company")

	def get_object(self, queryset=None):
		return CompanySettings.load()

	def form_valid(self, form):
		messages.success(self.request, "Configuración de la empresa actualizada.")
		return super().form_valid(form)


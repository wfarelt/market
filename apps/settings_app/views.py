from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.core.exceptions import ValidationError
from django.views.generic import FormView, UpdateView

from apps.users.models import User
from .forms import BusinessDateForm, CompanySettingsForm
from .models import BusinessDateChange, BusinessDateSettings, CompanySettings
from .services import change_business_date, get_business_date


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


class BusinessDateView(LoginRequiredMixin, UserPassesTestMixin, FormView):
	form_class = BusinessDateForm
	template_name = "settings_app/business_date.html"
	success_url = reverse_lazy("settings_app:business-date")

	def test_func(self):
		return self.request.user.is_active and self.request.user.role in {
			User.ROLE_SUPERADMIN, User.ROLE_ADMIN, User.ROLE_CAJERO, User.ROLE_ALMACENERO,
		}

	def get_initial(self):
		settings = BusinessDateSettings.objects.get(pk=1)
		return {"mode": settings.mode, "business_date": settings.business_date}

	def form_valid(self, form):
		try:
			change_business_date(user=self.request.user, **form.cleaned_data)
		except ValidationError as error:
			form.add_error(None, error)
			return self.form_invalid(form)
		messages.success(self.request, "Fecha de trabajo actualizada.")
		return super().form_valid(form)

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context["business_date"] = get_business_date()
		context["changes"] = BusinessDateChange.objects.select_related("created_by")[:20]
		return context


def company_settings(request):
	return {
		"company_settings": CompanySettings.load(),
		"business_date_settings": BusinessDateSettings.objects.get(pk=1),
	}

from django.views.generic import TemplateView

from apps.settings_app.models import BusinessDateSettings
from apps.settings_app.services import get_business_date

from .forms import ReportFilterForm
from .permissions import ReportAccessMixin
from .selectors import DATE_BASIS_BUSINESS, DATE_BASIS_PREVIOUS, get_report_summary


class ReportDashboardView(ReportAccessMixin, TemplateView):
	template_name = "reports/index.html"

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		settings = BusinessDateSettings.objects.get(pk=1)
		default_date = get_business_date()
		default_basis = DATE_BASIS_BUSINESS if settings.mode == BusinessDateSettings.MODE_HISTORICAL else DATE_BASIS_PREVIOUS
		filters = self.request.GET.copy()
		for name, value in (("date_basis", default_basis), ("start_date", default_date.isoformat()), ("end_date", default_date.isoformat())):
			if not filters.get(name):
				filters[name] = value
		form = ReportFilterForm(filters, user=self.request.user, default_date=default_date, default_basis=default_basis)
		context["form"] = form
		if form.is_valid():
			cleaned_data = form.cleaned_data
			start_date = cleaned_data.get("start_date") or default_date
			end_date = cleaned_data.get("end_date") or default_date
			if start_date > end_date:
				form.add_error(None, "La fecha inicial no puede ser posterior a la fecha final.")
				return context
			context["date_basis"] = cleaned_data.get("date_basis") or default_basis
			context["report"] = get_report_summary(
				user=self.request.user,
				branch=cleaned_data.get("branch"),
				start_date=start_date,
				end_date=end_date,
				date_basis=context["date_basis"],
			)
		return context

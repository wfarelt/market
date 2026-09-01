from django.utils import timezone
from django.views.generic import TemplateView

from .forms import ReportFilterForm
from .permissions import ReportAccessMixin
from .selectors import get_report_summary


class ReportDashboardView(ReportAccessMixin, TemplateView):
	template_name = "reports/index.html"

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		form = ReportFilterForm(self.request.GET or None, user=self.request.user)
		form_is_valid = form.is_valid()
		cleaned_data = form.cleaned_data if form_is_valid else {}
		start_date = cleaned_data.get("start_date") or timezone.localdate()
		end_date = cleaned_data.get("end_date") or timezone.localdate()
		branch = cleaned_data.get("branch") if "branch" in form.fields else None
		context["form"] = form
		context["report"] = get_report_summary(
			user=self.request.user,
			branch=branch,
			start_date=start_date,
			end_date=end_date,
		)
		return context


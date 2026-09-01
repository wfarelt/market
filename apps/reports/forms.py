from django import forms
from django.utils import timezone

from apps.branches.models import Branch
from apps.users.models import User


class ReportFilterForm(forms.Form):
	start_date = forms.DateField(required=False, label="Desde", widget=forms.DateInput(attrs={"type": "date"}))
	end_date = forms.DateField(required=False, label="Hasta", widget=forms.DateInput(attrs={"type": "date"}))
	branch = forms.ModelChoiceField(queryset=Branch.objects.none(), required=False, label="Sucursal")

	def __init__(self, *args, user, **kwargs):
		super().__init__(*args, **kwargs)
		for field_name in ["start_date", "end_date"]:
			self.fields[field_name].widget.attrs["class"] = "form-control"
			if not self.is_bound:
				self.initial[field_name] = timezone.localdate()
		if user.role == User.ROLE_SUPERADMIN:
			self.fields["branch"].queryset = Branch.objects.filter(is_active=True)
			self.fields["branch"].widget.attrs["class"] = "form-select"
		else:
			self.fields.pop("branch")


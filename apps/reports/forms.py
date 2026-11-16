from django import forms

from apps.branches.models import Branch
from apps.users.models import User

from .selectors import DATE_BASIS_CHOICES


class ReportFilterForm(forms.Form):
	date_basis = forms.ChoiceField(choices=DATE_BASIS_CHOICES, label="Criterio de fecha")
	start_date = forms.DateField(required=False, label="Desde", widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}))
	end_date = forms.DateField(required=False, label="Hasta", widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}))
	branch = forms.ModelChoiceField(queryset=Branch.objects.none(), required=False, label="Sucursal")

	def __init__(self, *args, user, default_date, default_basis, **kwargs):
		super().__init__(*args, **kwargs)
		self.fields["date_basis"].widget.attrs["class"] = "form-select"
		self.fields["date_basis"].required = False
		self.initial["date_basis"] = default_basis
		for field_name in ["start_date", "end_date"]:
			self.fields[field_name].widget.attrs["class"] = "form-control"
			if not self.is_bound:
				self.initial[field_name] = default_date
		if user.role == User.ROLE_SUPERADMIN:
			self.fields["branch"].queryset = Branch.objects.filter(is_active=True)
			self.fields["branch"].widget.attrs["class"] = "form-select"
		else:
			self.fields.pop("branch")

	def clean(self):
		cleaned_data = super().clean()
		start_date = cleaned_data.get("start_date")
		end_date = cleaned_data.get("end_date")
		if start_date and end_date and start_date > end_date:
			raise forms.ValidationError("La fecha inicial no puede ser posterior a la fecha final.")
		return cleaned_data

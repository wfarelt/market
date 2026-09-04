from django import forms

from .models import CompanySettings


class CompanySettingsForm(forms.ModelForm):
	class Meta:
		model = CompanySettings
		fields = ["name", "trade_name", "tax_id", "address", "phone", "email"]
		widgets = {
			"name": forms.TextInput(attrs={"class": "form-control"}),
			"trade_name": forms.TextInput(attrs={"class": "form-control"}),
			"tax_id": forms.TextInput(attrs={"class": "form-control"}),
			"address": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
			"phone": forms.TextInput(attrs={"class": "form-control"}),
			"email": forms.EmailInput(attrs={"class": "form-control"}),
		}


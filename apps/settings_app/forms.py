from django import forms

from .models import CompanySettings


class CompanySettingsForm(forms.ModelForm):
	class Meta:
		model = CompanySettings
		fields = [
			"name", "trade_name", "tax_id", "address", "phone", "email",
			"enable_cash_payment", "enable_qr_payment", "enable_card_payment",
			"enable_transfer_payment", "enable_credit_payment",
		]
		widgets = {
			"name": forms.TextInput(attrs={"class": "form-control"}),
			"trade_name": forms.TextInput(attrs={"class": "form-control"}),
			"tax_id": forms.TextInput(attrs={"class": "form-control"}),
			"address": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
			"phone": forms.TextInput(attrs={"class": "form-control"}),
			"email": forms.EmailInput(attrs={"class": "form-control"}),
			"enable_cash_payment": forms.CheckboxInput(attrs={"class": "form-check-input"}),
			"enable_qr_payment": forms.CheckboxInput(attrs={"class": "form-check-input"}),
			"enable_card_payment": forms.CheckboxInput(attrs={"class": "form-check-input"}),
			"enable_transfer_payment": forms.CheckboxInput(attrs={"class": "form-check-input"}),
			"enable_credit_payment": forms.CheckboxInput(attrs={"class": "form-check-input"}),
		}


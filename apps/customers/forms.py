from django import forms
from .models import Customer


class CustomerForm(forms.ModelForm):
	class Meta:
		model = Customer
		fields = ["first_name", "last_name", "id_document", "tax_id", "phone", "address", "email", "is_active"]

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		for field in self.fields.values():
			if isinstance(field.widget, forms.CheckboxInput):
				field.widget.attrs["class"] = "form-check-input"
			else:
				field.widget.attrs["class"] = "form-control"


class CreditPaymentForm(forms.Form):
	amount = forms.DecimalField(
		max_digits=12,
		decimal_places=2,
		min_value=0.01,
		label="Monto a pagar",
		widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "placeholder": "0.00"}),
	)
	notes = forms.CharField(
		required=False,
		label="Observaciones",
		widget=forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Detalle u observación opcional..."}),
	)


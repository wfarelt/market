from django import forms
from apps.customers.models import Customer
from .models import Sale


class CheckoutForm(forms.Form):
	payment_method = forms.ChoiceField(choices=Sale.PAYMENT_CHOICES, label="Método de pago")
	customer = forms.ModelChoiceField(
		queryset=Customer.objects.filter(is_active=True),
		required=False,
		label="Cliente",
		empty_label="-- Seleccionar Cliente --",
	)
	cash_received = forms.DecimalField(required=False, max_digits=12, decimal_places=2, min_value=0, label="Efectivo recibido")

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.fields["payment_method"].widget.attrs["class"] = "form-select"
		self.fields["customer"].widget.attrs["class"] = "form-select"
		self.fields["cash_received"].widget.attrs.update({"class": "form-control", "step": "0.01"})

	def clean(self):
		cleaned_data = super().clean()
		payment_method = cleaned_data.get("payment_method")
		customer = cleaned_data.get("customer")
		if payment_method == Sale.PAYMENT_CREDIT and not customer:
			self.add_error("customer", "Debes seleccionar un cliente para realizar una venta a crédito.")
		return cleaned_data


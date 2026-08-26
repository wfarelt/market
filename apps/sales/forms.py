from django import forms

from .models import Sale


class CheckoutForm(forms.Form):
	payment_method = forms.ChoiceField(choices=[choice for choice in Sale.PAYMENT_CHOICES if choice[0] != Sale.PAYMENT_CREDIT], label="Método de pago")
	cash_received = forms.DecimalField(required=False, max_digits=12, decimal_places=2, min_value=0, label="Efectivo recibido")

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.fields["payment_method"].widget.attrs["class"] = "form-select"
		self.fields["cash_received"].widget.attrs.update({"class": "form-control", "step": "0.01"})


from decimal import Decimal

from django import forms
from django.utils import timezone

from apps.customers.models import Customer
from apps.settings_app.models import CompanySettings
from apps.users.models import User

from .models import Sale


class CheckoutForm(forms.Form):
	payment_method = forms.ChoiceField(choices=Sale.PAYMENT_CHOICES, label="Método de pago")
	sale_date = forms.DateField(
		label="Fecha de venta",
		widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date", "class": "form-control"}),
	)
	customer = forms.ModelChoiceField(
		queryset=Customer.objects.filter(is_active=True),
		required=False,
		label="Cliente",
		empty_label="-- Seleccionar Cliente --",
	)
	discount_amount = forms.DecimalField(
		required=False,
		min_value=0,
		max_digits=12,
		decimal_places=2,
		label="Descuento",
		initial=Decimal("0.00"),
	)
	cash_received = forms.DecimalField(required=False, max_digits=12, decimal_places=2, min_value=0, label="Efectivo recibido")

	def __init__(self, *args, user, **kwargs):
		super().__init__(*args, **kwargs)
		if user.role != User.ROLE_ADMIN:
			self.fields.pop("sale_date")
		else:
			self.initial.setdefault("sale_date", timezone.localdate())
		self.fields["payment_method"].choices = CompanySettings.load().enabled_payment_choices(Sale.PAYMENT_CHOICES)
		self.fields["payment_method"].widget.attrs["class"] = "form-select"
		self.fields["customer"].widget.attrs["class"] = "form-select"
		self.fields["discount_amount"].widget.attrs.update({
			"class": "form-control form-control-sm text-end font-monospace",
			"step": "0.01",
			"min": "0",
			"placeholder": "0.00",
		})
		self.fields["cash_received"].widget.attrs.update({"class": "form-control text-end font-monospace", "step": "0.01"})

	def clean(self):
		cleaned_data = super().clean()
		payment_method = cleaned_data.get("payment_method")
		customer = cleaned_data.get("customer")
		discount_amount = cleaned_data.get("discount_amount")
		if payment_method == Sale.PAYMENT_CREDIT and not customer:
			self.add_error("customer", "Debes seleccionar un cliente para realizar una venta a crédito.")
		if discount_amount is not None and discount_amount < 0:
			self.add_error("discount_amount", "El descuento no puede ser negativo.")
		return cleaned_data

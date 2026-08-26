from django import forms
from django.forms import BaseInlineFormSet, inlineformset_factory

from .models import InventoryMovement, InventoryMovementLine, Stock


class StockInitialForm(forms.ModelForm):
	class Meta:
		model = Stock
		fields = ["product", "branch", "quantity"]

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		for field in self.fields.values():
			if isinstance(field.widget, forms.Select):
				field.widget.attrs["class"] = "form-select"
			else:
				field.widget.attrs["class"] = "form-control"


class InventoryMovementForm(forms.ModelForm):
	class Meta:
		model = InventoryMovement
		fields = ["movement_type", "branch", "notes"]

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.fields["movement_type"].choices = [
			choice for choice in InventoryMovement.TYPE_CHOICES
			if choice[0] != InventoryMovement.TYPE_TRANSFER
		]
		self.fields["movement_type"].widget.attrs["class"] = "form-select"
		self.fields["branch"].widget.attrs["class"] = "form-select"
		self.fields["notes"].widget.attrs["class"] = "form-control"


class InventoryMovementLineForm(forms.ModelForm):
	class Meta:
		model = InventoryMovementLine
		fields = ["product", "quantity", "adjustment_direction"]

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.fields["product"].widget.attrs["class"] = "form-select"
		self.fields["quantity"].widget.attrs["class"] = "form-control"
		self.fields["adjustment_direction"].widget.attrs["class"] = "form-select"


class InventoryMovementLineFormSetBase(BaseInlineFormSet):
	def clean(self):
		super().clean()
		if any(self.errors):
			return
		if not any(form.cleaned_data and not form.cleaned_data.get("DELETE") for form in self.forms):
			raise forms.ValidationError("Agrega al menos un producto al movimiento.")


InventoryMovementLineFormSet = inlineformset_factory(
	InventoryMovement,
	InventoryMovementLine,
	form=InventoryMovementLineForm,
	formset=InventoryMovementLineFormSetBase,
	extra=1,
	can_delete=True,
)


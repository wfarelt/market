from django import forms
from django.forms import BaseInlineFormSet, inlineformset_factory

from .models import Purchase, PurchaseItem


class PurchaseForm(forms.ModelForm):
	class Meta:
		model = Purchase
		fields = ["notes"]
		widgets = {"notes": forms.Textarea(attrs={"rows": 2})}

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.fields["notes"].widget.attrs["class"] = "form-control"


class PurchaseItemForm(forms.ModelForm):
	class Meta:
		model = PurchaseItem
		fields = ["product", "quantity", "unit_cost", "sale_price", "update_cost", "update_sale_price"]

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.fields["product"].widget.attrs["class"] = "form-select"
		for field_name in ["quantity", "unit_cost", "sale_price"]:
			self.fields[field_name].widget.attrs.update({"class": "form-control", "step": "0.01"})
		for field_name in ["update_cost", "update_sale_price"]:
			self.fields[field_name].widget.attrs["class"] = "form-check-input"


class PurchaseItemFormSetBase(BaseInlineFormSet):
	def clean(self):
		super().clean()
		if any(self.errors):
			return
		if not any(form.cleaned_data and not form.cleaned_data.get("DELETE") for form in self.forms):
			raise forms.ValidationError("Agrega al menos un producto a la compra.")


PurchaseItemFormSet = inlineformset_factory(Purchase, PurchaseItem, form=PurchaseItemForm, formset=PurchaseItemFormSetBase, extra=1, can_delete=True)


from django import forms
from django.forms import BaseInlineFormSet, inlineformset_factory

from .models import Transfer, TransferItem


class TransferForm(forms.ModelForm):
	class Meta:
		model = Transfer
		fields = ["origin_branch", "destination_branch", "notes"]

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		for field in self.fields.values():
			field.widget.attrs["class"] = "form-select" if isinstance(field.widget, forms.Select) else "form-control"


class TransferItemForm(forms.ModelForm):
	class Meta:
		model = TransferItem
		fields = ["product", "requested_quantity"]

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.fields["product"].queryset = self.fields["product"].queryset.filter(is_active=True)
		self.fields["product"].widget.attrs["class"] = "form-select"
		self.fields["requested_quantity"].widget.attrs.update({"class": "form-control", "min": "0.01", "step": "0.01"})


class RequiredItemFormSet(BaseInlineFormSet):
	def clean(self):
		super().clean()
		if not any(form.cleaned_data and not form.cleaned_data.get("DELETE") for form in self.forms):
			raise forms.ValidationError("Agrega al menos un producto.")


TransferItemFormSet = inlineformset_factory(Transfer, TransferItem, form=TransferItemForm, formset=RequiredItemFormSet, extra=1, can_delete=True)


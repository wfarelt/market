from django import forms
from django.forms import BaseInlineFormSet, inlineformset_factory
from django.utils import timezone

from apps.branches.models import Branch

from .models import InventoryMovement, InventoryMovementLine, Stock


class InventoryMovementFilterForm(forms.Form):
	q = forms.CharField(required=False, label="Buscar")
	start_date = forms.DateField(required=False, label="Desde", widget=forms.DateInput(attrs={"type": "date"}))
	end_date = forms.DateField(required=False, label="Hasta", widget=forms.DateInput(attrs={"type": "date"}))
	movement_type = forms.ChoiceField(required=False, label="Tipo")
	branch = forms.ModelChoiceField(queryset=Branch.objects.none(), required=False, label="Sucursal")
	status = forms.ChoiceField(required=False, label="Estado")

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.fields["movement_type"].choices = [("", "Todos los tipos"), *InventoryMovement.TYPE_CHOICES]
		self.fields["status"].choices = [("", "Todos los estados"), *InventoryMovement.STATUS_CHOICES]
		self.fields["branch"].queryset = Branch.objects.filter(is_active=True)
		self.fields["q"].widget.attrs.update({"class": "form-control", "placeholder": "Notas, sucursal o usuario"})
		for field_name in ["start_date", "end_date"]:
			self.fields[field_name].widget.attrs["class"] = "form-control"
		for field_name in ["movement_type", "branch", "status"]:
			self.fields[field_name].widget.attrs["class"] = "form-select"

	def clean(self):
		cleaned_data = super().clean()
		start_date = cleaned_data.get("start_date")
		end_date = cleaned_data.get("end_date")
		if start_date and end_date and start_date > end_date:
			raise forms.ValidationError("La fecha inicial no puede ser posterior a la fecha final.")
		return cleaned_data


class StockFilterForm(forms.Form):
	branch = forms.ModelChoiceField(
		queryset=Branch.objects.filter(is_active=True),
		required=False,
		label="Sucursal",
		empty_label="Todas las sucursales",
	)

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.fields["branch"].widget.attrs["class"] = "form-select"


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
		self.fields["quantity"].widget.attrs["step"] = "1"


class InventoryMovementForm(forms.ModelForm):
	class Meta:
		model = InventoryMovement
		fields = ["movement_date", "movement_type", "branch", "notes"]

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.fields["movement_type"].choices = [
			choice for choice in InventoryMovement.TYPE_CHOICES
			if choice[0] != InventoryMovement.TYPE_TRANSFER
		]
		self.fields["movement_type"].widget.attrs["class"] = "form-select"
		self.fields["branch"].widget.attrs["class"] = "form-select"
		self.fields["notes"].widget.attrs["class"] = "form-control"
		self.fields["notes"].widget.attrs["rows"] = 2
		self.fields["movement_date"].widget.attrs["class"] = "form-control"
		self.fields["movement_date"].required = False

	def clean_movement_date(self):
		return self.cleaned_data.get("movement_date") or timezone.localdate()


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


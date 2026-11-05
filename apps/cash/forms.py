from django import forms

from .models import ExpenseCategory


class ExpenseCategoryForm(forms.ModelForm):
	class Meta:
		model = ExpenseCategory
		fields = ["name", "is_active"]

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.fields["name"].widget.attrs["class"] = "form-control"
		self.fields["is_active"].widget.attrs["class"] = "form-check-input"


class CashRegisterOpenForm(forms.Form):
	opening_amount = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0, label="Fondo de apertura")
	notes = forms.CharField(required=False, widget=forms.Textarea, label="Observaciones")

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.fields["opening_amount"].widget.attrs.update({"class": "form-control", "step": "0.01"})
		self.fields["notes"].widget.attrs["class"] = "form-control"


class CashRegisterCloseForm(forms.Form):
	closing_amount = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0, label="Monto contado")

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.fields["closing_amount"].widget.attrs.update({"class": "form-control", "step": "0.01"})


class CashClosureCorrectionForm(forms.Form):
	closing_amount = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0, label="Monto contado corregido")
	reason = forms.CharField(label="Motivo de la rectificación", widget=forms.Textarea(attrs={"rows": 3}))

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.fields["closing_amount"].widget.attrs.update({"class": "form-control", "step": "0.01"})
		self.fields["reason"].widget.attrs.update({"class": "form-control", "maxlength": 2000})

	def clean_reason(self):
		reason = self.cleaned_data["reason"].strip()
		if not reason:
			raise forms.ValidationError("Indica el motivo de la rectificación.")
		return reason


class PettyCashExpenseForm(forms.Form):
	category = forms.ModelChoiceField(queryset=ExpenseCategory.objects.none(), label="Categoría")
	concept = forms.CharField(max_length=255, label="Concepto")
	amount = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0.01, label="Monto")

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.fields["category"].queryset = ExpenseCategory.objects.filter(is_active=True)
		self.fields["category"].widget.attrs["class"] = "form-select"
		self.fields["concept"].widget.attrs["class"] = "form-control"
		self.fields["amount"].widget.attrs.update({"class": "form-control", "step": "0.01"})


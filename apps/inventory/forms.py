from django import forms

from .models import Stock


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


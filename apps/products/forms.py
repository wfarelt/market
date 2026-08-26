from django import forms

from .models import Brand, Category, Product, UnitMeasure


class StyledModelForm(forms.ModelForm):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		for field in self.fields.values():
			if isinstance(field.widget, forms.CheckboxInput):
				field.widget.attrs["class"] = "form-check-input"
			elif isinstance(field.widget, forms.Select):
				field.widget.attrs["class"] = "form-select"
			else:
				field.widget.attrs["class"] = "form-control"


class CategoryForm(StyledModelForm):
	class Meta:
		model = Category
		fields = ["name", "code", "description", "is_active"]


class BrandForm(StyledModelForm):
	class Meta:
		model = Brand
		fields = ["name", "code", "description", "is_active"]


class UnitMeasureForm(StyledModelForm):
	class Meta:
		model = UnitMeasure
		fields = ["name", "code", "symbol", "description", "is_active"]


class ProductForm(StyledModelForm):
	class Meta:
		model = Product
		fields = [
			"name",
			"sku",
			"description",
			"category",
			"brand",
			"unit_measure",
			"list_price",
			"is_active",
		]


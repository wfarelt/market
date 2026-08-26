from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import User


class UserManagementForm(forms.ModelForm):
	class Meta:
		model = User
		fields = ["username", "first_name", "last_name", "email", "branch", "role", "is_active"]

	def __init__(self, *args, actor, **kwargs):
		super().__init__(*args, **kwargs)
		if actor.role == User.ROLE_ADMIN:
			self.fields["role"].choices = [
				choice for choice in User.ROLE_CHOICES
				if choice[0] != User.ROLE_SUPERADMIN
			]
		for field in self.fields.values():
			if isinstance(field.widget, forms.CheckboxInput):
				field.widget.attrs["class"] = "form-check-input"
			elif isinstance(field.widget, forms.Select):
				field.widget.attrs["class"] = "form-select"
			else:
				field.widget.attrs["class"] = "form-control"


class UserManagementCreationForm(UserCreationForm):
	class Meta(UserCreationForm.Meta):
		model = User
		fields = [
			"username",
			"first_name",
			"last_name",
			"email",
			"branch",
			"role",
			"is_active",
		]

	def __init__(self, *args, actor, **kwargs):
		super().__init__(*args, **kwargs)
		if actor.role == User.ROLE_ADMIN:
			self.fields["role"].choices = [
				choice for choice in User.ROLE_CHOICES
				if choice[0] != User.ROLE_SUPERADMIN
			]
		for field in self.fields.values():
			if isinstance(field.widget, forms.CheckboxInput):
				field.widget.attrs["class"] = "form-check-input"
			elif isinstance(field.widget, forms.Select):
				field.widget.attrs["class"] = "form-select"
			else:
				field.widget.attrs["class"] = "form-control"


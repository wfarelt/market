from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from .models import User


class MarketUserChangeForm(UserChangeForm):
	class Meta(UserChangeForm.Meta):
		model = User


class MarketUserCreationForm(UserCreationForm):
	class Meta(UserCreationForm.Meta):
		model = User
		fields = ("username", "branch", "role")


@admin.register(User)
class MarketUserAdmin(UserAdmin):
	form = MarketUserChangeForm
	add_form = MarketUserCreationForm
	fieldsets = UserAdmin.fieldsets + (
		("Asignacion", {"fields": ("branch", "role")}),
	)
	add_fieldsets = (
		(
			None,
			{
				"classes": ("wide",),
				"fields": ("username", "password1", "password2", "branch", "role"),
			},
		),
	)
	list_display = ["username", "first_name", "last_name", "branch", "role", "is_active"]
	list_filter = ["role", "branch", "is_active", "is_staff"]


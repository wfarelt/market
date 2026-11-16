from django.urls import path

from . import views

app_name = "settings_app"

urlpatterns = [
	path("empresa/", views.CompanySettingsView.as_view(), name="company"),
	path("fecha-trabajo/", views.BusinessDateView.as_view(), name="business-date"),
]

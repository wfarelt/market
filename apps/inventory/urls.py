from django.urls import path

from . import views

app_name = "inventory"

urlpatterns = [
	path("", views.StockListView.as_view(), name="list"),
	path("create/", views.StockCreateView.as_view(), name="create"),
]


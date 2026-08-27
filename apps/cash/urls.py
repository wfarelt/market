from django.urls import path

from . import views

app_name = "cash"

urlpatterns = [
	path("", views.CashRegisterListView.as_view(), name="list"),
	path("open/", views.CashRegisterOpenView.as_view(), name="open"),
	path("<int:pk>/", views.CashRegisterDetailView.as_view(), name="detail"),
	path("<int:pk>/close/", views.CashRegisterCloseView.as_view(), name="close"),
	path("<int:pk>/expenses/create/", views.PettyCashExpenseCreateView.as_view(), name="expense-create"),
]


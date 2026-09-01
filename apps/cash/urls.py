from django.urls import path

from . import views

app_name = "cash"

urlpatterns = [
	path("", views.CashRegisterListView.as_view(), name="list"),
	path("expense-categories/", views.ExpenseCategoryListView.as_view(), name="category-list"),
	path("expense-categories/create/", views.ExpenseCategoryCreateView.as_view(), name="category-create"),
	path("expense-categories/<int:pk>/edit/", views.ExpenseCategoryUpdateView.as_view(), name="category-update"),
	path("open/", views.CashRegisterOpenView.as_view(), name="open"),
	path("<int:pk>/", views.CashRegisterDetailView.as_view(), name="detail"),
	path("<int:pk>/close/", views.CashRegisterCloseView.as_view(), name="close"),
	path("<int:pk>/expenses/create/", views.PettyCashExpenseCreateView.as_view(), name="expense-create"),
]


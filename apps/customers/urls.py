from django.urls import path
from . import views

app_name = "customers"

urlpatterns = [
	path("", views.CustomerListView.as_view(), name="list"),
	path("create/", views.CustomerCreateView.as_view(), name="create"),
	path("<int:pk>/", views.CustomerDetailView.as_view(), name="detail"),
	path("<int:pk>/update/", views.CustomerUpdateView.as_view(), name="update"),
	path("<int:pk>/toggle-active/", views.CustomerToggleActiveView.as_view(), name="toggle-active"),
	path("<int:pk>/account-statement/", views.CustomerAccountStatementView.as_view(), name="account-statement"),
	path("credits/", views.CreditListView.as_view(), name="credit-list"),
	path("credits/<int:pk>/", views.CreditDetailView.as_view(), name="credit-detail"),
	path("credits/<int:pk>/pay/", views.CreditPaymentCreateView.as_view(), name="credit-payment"),
]


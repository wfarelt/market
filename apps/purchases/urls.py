from django.urls import path

from . import views

app_name = "purchases"

urlpatterns = [
	path("", views.PurchaseListView.as_view(), name="list"),
	path("create/", views.PurchaseCreateView.as_view(), name="create"),
	path("<int:pk>/", views.PurchaseDetailView.as_view(), name="detail"),
	path("<int:pk>/update/", views.PurchaseUpdateView.as_view(), name="update"),
	path("<int:pk>/confirm/", views.PurchaseConfirmView.as_view(), name="confirm"),
	path("<int:pk>/cancel/", views.PurchaseCancelView.as_view(), name="cancel"),
]


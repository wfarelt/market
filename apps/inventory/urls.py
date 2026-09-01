from django.urls import path

from . import views

app_name = "inventory"

urlpatterns = [
	path("", views.StockListView.as_view(), name="list"),
	path("create/", views.StockCreateView.as_view(), name="create"),
	path("stock-availability/", views.StockAvailabilityView.as_view(), name="stock-availability"),
	path("movements/", views.InventoryMovementListView.as_view(), name="movement-list"),
	path("movements/create/", views.InventoryMovementCreateView.as_view(), name="movement-create"),
	path("movements/<int:pk>/", views.InventoryMovementDetailView.as_view(), name="movement-detail"),
	path("movements/<int:pk>/edit/", views.InventoryMovementUpdateView.as_view(), name="movement-update"),
	path("movements/<int:pk>/post/", views.InventoryMovementPostView.as_view(), name="movement-post"),
]


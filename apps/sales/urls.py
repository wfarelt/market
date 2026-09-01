from django.urls import path

from . import views

app_name = "sales"

urlpatterns = [
	path("", views.PosView.as_view(), name="pos"),
	path("list/", views.SaleListView.as_view(), name="list"),
	path("items/<int:product_id>/add/", views.PosAddItemView.as_view(), name="add-item"),
	path("items/<int:item_id>/update/", views.PosUpdateItemView.as_view(), name="update-item"),
	path("cart/clear/", views.PosClearCartView.as_view(), name="clear-cart"),
	path("checkout/", views.PosCheckoutView.as_view(), name="checkout"),
	path("<int:pk>/", views.SaleDetailView.as_view(), name="detail"),
]


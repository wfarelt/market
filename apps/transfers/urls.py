from django.urls import path
from . import views

app_name = "transfers"

urlpatterns = [path("", views.TransferListView.as_view(), name="list"), path("stock-availability/", views.TransferStockAvailabilityView.as_view(), name="stock-availability"), path("create/", views.TransferCreateView.as_view(), name="create"), path("<int:pk>/", views.TransferDetailView.as_view(), name="detail"), path("<int:pk>/edit/", views.TransferUpdateView.as_view(), name="update"), path("<int:pk>/send/", views.TransferSendView.as_view(), name="send"), path("<int:pk>/receive/", views.TransferReceiveView.as_view(), name="receive"), path("<int:pk>/cancel/", views.TransferCancelView.as_view(), name="cancel")]


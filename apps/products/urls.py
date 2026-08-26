from django.urls import path

from . import views

app_name = "products"

urlpatterns = [
	path("", views.ProductListView.as_view(), name="list"),
	path("create/", views.ProductCreateView.as_view(), name="create"),
	path("<int:pk>/edit/", views.ProductUpdateView.as_view(), name="update"),
	path("<int:pk>/delete/", views.ProductDeleteView.as_view(), name="delete"),
	path("categories/", views.CategoryListView.as_view(), name="category-list"),
	path("categories/create/", views.CategoryCreateView.as_view(), name="category-create"),
	path("categories/<int:pk>/edit/", views.CategoryUpdateView.as_view(), name="category-update"),
	path("categories/<int:pk>/delete/", views.CategoryDeleteView.as_view(), name="category-delete"),
	path("brands/", views.BrandListView.as_view(), name="brand-list"),
	path("brands/create/", views.BrandCreateView.as_view(), name="brand-create"),
	path("brands/<int:pk>/edit/", views.BrandUpdateView.as_view(), name="brand-update"),
	path("brands/<int:pk>/delete/", views.BrandDeleteView.as_view(), name="brand-delete"),
	path("units/", views.UnitMeasureListView.as_view(), name="unit-measure-list"),
	path("units/create/", views.UnitMeasureCreateView.as_view(), name="unit-measure-create"),
	path("units/<int:pk>/edit/", views.UnitMeasureUpdateView.as_view(), name="unit-measure-update"),
	path("units/<int:pk>/delete/", views.UnitMeasureDeleteView.as_view(), name="unit-measure-delete"),
]


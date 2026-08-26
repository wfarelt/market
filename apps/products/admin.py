from django.contrib import admin

from .models import Brand, Category, Product, UnitMeasure


class CatalogAdmin(admin.ModelAdmin):
	list_display = ["code", "name", "is_active"]
	list_filter = ["is_active"]
	search_fields = ["code", "name"]


@admin.register(Category)
class CategoryAdmin(CatalogAdmin):
	pass


@admin.register(Brand)
class BrandAdmin(CatalogAdmin):
	pass


@admin.register(UnitMeasure)
class UnitMeasureAdmin(CatalogAdmin):
	list_display = ["code", "name", "symbol", "is_active"]
	search_fields = ["code", "name", "symbol"]


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
	list_display = ["sku", "name", "category", "brand", "unit_measure", "list_price", "is_active"]
	list_filter = ["is_active", "category", "brand", "unit_measure"]
	search_fields = ["sku", "name"]


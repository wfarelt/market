from django.contrib import admin

from apps.core.admin import ReadOnlyAdminMixin

from .models import InventoryMovement, InventoryMovementLine, Stock


@admin.register(Stock)
class StockAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
	list_display = ["product", "branch", "quantity", "updated_at"]
	list_filter = ["branch"]
	search_fields = ["product__sku", "product__name", "branch__code", "branch__name"]
	readonly_fields = ["created_at", "updated_at", "created_by"]

class InventoryMovementLineInline(ReadOnlyAdminMixin, admin.TabularInline):
	model = InventoryMovementLine
	extra = 0


@admin.register(InventoryMovement)
class InventoryMovementAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
	list_display = ["id", "movement_type", "branch", "status", "movement_date", "created_at", "posted_at"]
	list_filter = ["movement_type", "status", "branch"]
	search_fields = ["notes"]
	readonly_fields = ["created_at", "updated_at", "created_by", "posted_at"]
	inlines = [InventoryMovementLineInline]

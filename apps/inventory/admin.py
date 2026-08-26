from django.contrib import admin

from .models import InventoryMovement, InventoryMovementLine, Stock


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
	list_display = ["product", "branch", "quantity", "updated_at"]
	list_filter = ["branch"]
	search_fields = ["product__sku", "product__name", "branch__code", "branch__name"]
	readonly_fields = ["created_at", "updated_at", "created_by"]

	def get_readonly_fields(self, request, obj=None):
		if obj:
			return [*self.readonly_fields, "product", "branch", "quantity"]
		return self.readonly_fields


class InventoryMovementLineInline(admin.TabularInline):
	model = InventoryMovementLine
	extra = 1


@admin.register(InventoryMovement)
class InventoryMovementAdmin(admin.ModelAdmin):
	list_display = ["id", "movement_type", "branch", "status", "created_at"]
	list_filter = ["movement_type", "status", "branch"]
	search_fields = ["notes"]
	readonly_fields = ["created_at", "updated_at", "created_by"]
	inlines = [InventoryMovementLineInline]


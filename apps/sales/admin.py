from django.contrib import admin

from .models import Sale, SaleItem


class SaleItemInline(admin.TabularInline):
	model = SaleItem
	extra = 0
	readonly_fields = ["product", "quantity", "unit_price", "discount_amount", "subtotal"]


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
	list_display = ["number", "branch", "user", "status", "total", "created_at"]
	list_filter = ["status", "branch", "payment_method"]
	readonly_fields = ["number", "subtotal", "discount_amount", "total", "inventory_movement", "cash_movement", "completed_at"]
	inlines = [SaleItemInline]


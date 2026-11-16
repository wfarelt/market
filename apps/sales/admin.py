from django.contrib import admin

from apps.core.admin import ReadOnlyAdminMixin

from .models import Sale, SaleItem


class SaleItemInline(ReadOnlyAdminMixin, admin.TabularInline):
	model = SaleItem
	extra = 0
	readonly_fields = ["product", "quantity", "unit_price", "discount_amount", "subtotal"]


@admin.register(Sale)
class SaleAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
	list_display = ["number", "branch", "user", "status", "business_date", "total", "created_at"]
	list_filter = ["status", "branch", "payment_method"]
	readonly_fields = ["number", "subtotal", "discount_amount", "total", "inventory_movement", "cash_movement", "completed_at", "business_date", "confirmed_at"]
	inlines = [SaleItemInline]

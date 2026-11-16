from django.contrib import admin

from apps.core.admin import ReadOnlyAdminMixin

from .models import Purchase, PurchaseItem, Supplier


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
	list_display = ["name", "tax_id", "phone", "is_active"]
	list_filter = ["is_active"]
	search_fields = ["name", "tax_id", "phone"]


class PurchaseItemInline(ReadOnlyAdminMixin, admin.TabularInline):
	model = PurchaseItem
	extra = 0


@admin.register(Purchase)
class PurchaseAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
	list_display = ["number", "supplier", "purchase_date", "business_date", "invoice_number", "branch", "status", "created_at", "confirmed_at"]
	list_filter = ["status", "branch"]
	search_fields = ["number", "invoice_number", "supplier__name", "notes"]
	readonly_fields = ["business_date"]
	inlines = [PurchaseItemInline]

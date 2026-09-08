from django.contrib import admin

from .models import Purchase, PurchaseItem, Supplier


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
	list_display = ["name", "tax_id", "phone", "is_active"]
	list_filter = ["is_active"]
	search_fields = ["name", "tax_id", "phone"]


class PurchaseItemInline(admin.TabularInline):
	model = PurchaseItem
	extra = 0


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
	list_display = ["number", "supplier", "purchase_date", "invoice_number", "branch", "status", "created_at", "confirmed_at"]
	list_filter = ["status", "branch"]
	search_fields = ["number", "invoice_number", "supplier__name", "notes"]
	inlines = [PurchaseItemInline]


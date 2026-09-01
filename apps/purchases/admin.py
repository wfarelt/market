from django.contrib import admin

from .models import Purchase, PurchaseItem


class PurchaseItemInline(admin.TabularInline):
	model = PurchaseItem
	extra = 0


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
	list_display = ["number", "branch", "status", "created_at", "confirmed_at"]
	list_filter = ["status", "branch"]
	search_fields = ["number", "notes"]
	inlines = [PurchaseItemInline]


from django.contrib import admin

from apps.core.admin import ReadOnlyAdminMixin

from .models import Transfer, TransferItem


class TransferItemInline(ReadOnlyAdminMixin, admin.TabularInline):
	model = TransferItem
	extra = 0


@admin.register(Transfer)
class TransferAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
	list_display = ["number", "origin_branch", "destination_branch", "status", "business_date", "created_at"]
	list_filter = ["status", "origin_branch", "destination_branch"]
	readonly_fields = ["number", "business_date", "sent_at", "received_at", "cancelled_at", "outgoing_movement", "incoming_movement"]
	inlines = [TransferItemInline]

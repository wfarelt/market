from django.contrib import admin

from .models import Transfer, TransferItem


class TransferItemInline(admin.TabularInline):
	model = TransferItem
	extra = 1


@admin.register(Transfer)
class TransferAdmin(admin.ModelAdmin):
	list_display = ["number", "origin_branch", "destination_branch", "status", "created_at"]
	list_filter = ["status", "origin_branch", "destination_branch"]
	readonly_fields = ["number", "sent_at", "received_at", "cancelled_at", "outgoing_movement", "incoming_movement"]
	inlines = [TransferItemInline]


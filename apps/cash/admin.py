from django.contrib import admin

from apps.core.admin import ReadOnlyAdminMixin

from .models import CashClosureCorrection, CashMovement, CashRegister, ExpenseCategory, PettyCashExpense


class CashMovementInline(ReadOnlyAdminMixin, admin.TabularInline):
	model = CashMovement
	extra = 0
	readonly_fields = ["movement_type", "amount", "description", "created_at", "created_by"]
	can_delete = False

@admin.register(CashRegister)
class CashRegisterAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
	list_display = ["id", "user", "branch", "status", "business_date", "opening_amount", "opened_at"]
	list_filter = ["status", "branch"]
	readonly_fields = ["business_date", "opened_at", "closed_at", "created_at", "updated_at", "created_by"]
	inlines = [CashMovementInline]


@admin.register(CashClosureCorrection)
class CashClosureCorrectionAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
	list_display = ["cash_register", "previous_closing_amount", "corrected_closing_amount", "created_by", "created_at"]
	list_filter = ["cash_register__branch", "created_at"]
	readonly_fields = [
		"cash_register",
		"previous_closing_amount",
		"corrected_closing_amount",
		"reason",
		"created_by",
		"created_at",
		"updated_at",
	]

@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
	list_display = ["name", "is_active"]


@admin.register(PettyCashExpense)
class PettyCashExpenseAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
	list_display = ["concept", "category", "amount", "cash_register", "user", "created_at"]

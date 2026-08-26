from django.contrib import admin

from .models import CashMovement, CashRegister, ExpenseCategory, PettyCashExpense


class CashMovementInline(admin.TabularInline):
	model = CashMovement
	extra = 0
	readonly_fields = ["movement_type", "amount", "description", "created_at", "created_by"]
	can_delete = False


@admin.register(CashRegister)
class CashRegisterAdmin(admin.ModelAdmin):
	list_display = ["id", "user", "branch", "status", "opening_amount", "opened_at"]
	list_filter = ["status", "branch"]
	readonly_fields = ["opened_at", "closed_at", "created_at", "updated_at", "created_by"]
	inlines = [CashMovementInline]


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
	list_display = ["name", "is_active"]


@admin.register(PettyCashExpense)
class PettyCashExpenseAdmin(admin.ModelAdmin):
	list_display = ["concept", "category", "amount", "cash_register", "user", "created_at"]


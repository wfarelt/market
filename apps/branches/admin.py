from django.contrib import admin

from .models import Branch, UserBranch


class UserBranchInline(admin.TabularInline):
    model = UserBranch
    extra = 0


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "phone", "is_active", "created_at"]
    list_filter = ["is_active"]
    search_fields = ["name", "code"]
    readonly_fields = ["code", "created_at", "updated_at"]
    inlines = [UserBranchInline]


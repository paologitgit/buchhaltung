from django.contrib import admin

from .models import Account, FiscalYear, JournalEntry, JournalLine


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "account_type", "is_active", "is_bank_account")
    list_filter = ("account_type", "is_active", "is_bank_account")
    search_fields = ("code", "name")


@admin.register(FiscalYear)
class FiscalYearAdmin(admin.ModelAdmin):
    list_display = ("__str__", "is_closed", "closed_at")


class JournalLineInline(admin.TabularInline):
    model = JournalLine
    extra = 0


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display = ("date", "description", "fiscal_year", "is_locked", "created_by")
    list_filter = ("fiscal_year", "is_locked")
    inlines = [JournalLineInline]
    readonly_fields = ("created_by", "created_at")

from django.contrib import admin

from .models import Account, AccountGroup, FiscalYear, JournalEntry, JournalLine


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "account_type",
        "is_active",
        "is_bank_account",
        "saldobilanz_gruppe",
        "jahresrechnung_gruppe",
    )
    list_filter = ("account_type", "is_active", "is_bank_account")
    list_editable = ("saldobilanz_gruppe", "jahresrechnung_gruppe")
    search_fields = ("code", "name")


@admin.register(AccountGroup)
class AccountGroupAdmin(admin.ModelAdmin):
    list_display = ("tree", "code", "name", "account_type", "parent", "order")
    list_filter = ("tree", "account_type")
    ordering = ("tree", "order", "code")


@admin.register(FiscalYear)
class FiscalYearAdmin(admin.ModelAdmin):
    list_display = ("__str__", "is_closed", "closed_at", "gewinnruecklage_zuweisung")


class JournalLineInline(admin.TabularInline):
    model = JournalLine
    extra = 0


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display = ("date", "description", "fiscal_year", "is_locked", "created_by")
    list_filter = ("fiscal_year", "is_locked")
    inlines = [JournalLineInline]
    readonly_fields = ("created_by", "created_at")

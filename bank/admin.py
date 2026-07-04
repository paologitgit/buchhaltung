from django.contrib import admin

from .models import BankAccount, Bewegung, ImportBatch


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = ("name", "iban", "currency", "ledger_account", "is_active")


@admin.register(ImportBatch)
class ImportBatchAdmin(admin.ModelAdmin):
    list_display = ("filename", "bank_account", "imported_at", "imported_by", "row_count", "created_count", "duplicate_count")
    readonly_fields = [f.name for f in ImportBatch._meta.fields]


@admin.register(Bewegung)
class BewegungAdmin(admin.ModelAdmin):
    list_display = ("booking_date", "amount", "description", "bank_account", "status", "assigned_account")
    list_filter = ("status", "bank_account")
    search_fields = ("description", "reference")

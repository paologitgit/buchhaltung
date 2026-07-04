from django.contrib import admin

from .models import VatCode


@admin.register(VatCode)
class VatCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "label", "rate_percent", "direction", "clearing_account", "active")
    list_filter = ("direction", "active")

from django.contrib import admin

from .models import Beleg


@admin.register(Beleg)
class BelegAdmin(admin.ModelAdmin):
    list_display = ("original_filename", "document_type", "bewegung", "uploaded_by", "uploaded_at", "size_bytes")
    list_filter = ("document_type",)
    readonly_fields = ("content_type", "size_bytes", "uploaded_by", "uploaded_at")

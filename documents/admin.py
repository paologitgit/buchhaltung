from django.contrib import admin

from .models import Beleg, IgnoredDuplicateHash


@admin.register(Beleg)
class BelegAdmin(admin.ModelAdmin):
    list_display = ("original_filename", "document_type", "bewegung", "uploaded_by", "uploaded_at", "size_bytes")
    list_filter = ("document_type",)
    readonly_fields = ("content_type", "size_bytes", "uploaded_by", "uploaded_at")


@admin.register(IgnoredDuplicateHash)
class IgnoredDuplicateHashAdmin(admin.ModelAdmin):
    list_display = ("file_hash", "ignored_by", "ignored_at")
    readonly_fields = ("ignored_by", "ignored_at")

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls")),
    path("", include("accounts.urls")),
    path("bank/", include("bank.urls")),
    path("belege/", include("documents.urls")),
    path("ledger/", include("ledger.urls")),
]

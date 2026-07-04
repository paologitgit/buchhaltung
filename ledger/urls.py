from django.urls import path

from . import views

urlpatterns = [
    path("konten/", views.account_list, name="account_list"),
    path("journal/", views.journal_list, name="journal_list"),
    path("journal/export/<str:fmt>/", views.journal_export, name="journal_export"),
    path("geschaeftsjahre/", views.fiscal_year_list, name="fiscal_year_list"),
    path("geschaeftsjahre/neu/", views.fiscal_year_create, name="fiscal_year_create"),
    path("geschaeftsjahre/<int:pk>/abschliessen/", views.fiscal_year_close, name="fiscal_year_close"),
]

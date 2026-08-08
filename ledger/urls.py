from django.urls import path

from . import views

urlpatterns = [
    path("konten/", views.account_list, name="account_list"),
    path("auswertung/", views.auswertung, name="auswertung"),
    path("journal/", views.journal_list, name="journal_list"),
    path("journal/export/<str:fmt>/", views.journal_export, name="journal_export"),
    path("geschaeftsjahre/", views.fiscal_year_list, name="fiscal_year_list"),
    path("geschaeftsjahre/neu/", views.fiscal_year_create, name="fiscal_year_create"),
    path("geschaeftsjahre/<int:pk>/abschliessen/", views.fiscal_year_close, name="fiscal_year_close"),
    path("berichte/", views.berichte, name="berichte"),
    path("berichte/bilanz/", views.bericht_bilanz, name="bericht_bilanz"),
    path("berichte/erfolgsrechnung/", views.bericht_erfolgsrechnung, name="bericht_erfolgsrechnung"),
    path("berichte/saldobilanz/", views.bericht_saldobilanz, name="bericht_saldobilanz"),
    path("berichte/kontoblatt/", views.bericht_kontoblatt, name="bericht_kontoblatt"),
    path("berichte/pdf/<str:report>/", views.bericht_pdf, name="bericht_pdf"),
]

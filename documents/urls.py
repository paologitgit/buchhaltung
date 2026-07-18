from django.urls import path

from . import views

urlpatterns = [
    path("bewegung/<int:bewegung_id>/hochladen/", views.beleg_upload, name="beleg_upload"),
    path("alle/", views.beleg_list, name="beleg_list"),
    path("duplikate/", views.beleg_duplicates, name="beleg_duplicates"),
    path("duplikate/<str:file_hash>/zusammenfuehren/", views.beleg_duplicates_merge, name="beleg_duplicates_merge"),
    path("posteingang/", views.posteingang_list, name="posteingang_list"),
    path("posteingang/hochladen/", views.posteingang_upload, name="posteingang_upload"),
    path("posteingang/mehrfach-hochladen/", views.posteingang_bulk_upload, name="posteingang_bulk_upload"),
    path("abrechnung-scannen/", views.statement_scan_upload, name="statement_scan_upload"),
    path("abrechnung-scannen/pruefen/", views.statement_scan_review, name="statement_scan_review"),
    path("<int:pk>/", views.beleg_download, name="beleg_download"),
    path("<int:pk>/vorschau/", views.beleg_thumbnail, name="beleg_thumbnail"),
    path("<int:pk>/drehen/", views.beleg_rotate, name="beleg_rotate"),
    path("<int:pk>/loeschen/", views.beleg_delete, name="beleg_delete"),
    path("<int:pk>/zuweisen/", views.beleg_assign, name="beleg_assign"),
    path("<int:pk>/anhaengen/", views.beleg_copy, name="beleg_copy"),
    path("<int:pk>/ausblenden/", views.beleg_toggle_hidden, name="beleg_toggle_hidden"),
    path("<int:pk>/typ-aendern/", views.beleg_change_type, name="beleg_change_type"),
]

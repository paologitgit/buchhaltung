from django.urls import path

from . import views

urlpatterns = [
    path("import/", views.import_view, name="bewegung_import"),
    path("bewegungen/", views.bewegung_list, name="bewegung_list"),
    path("bewegungen/loeschen/", views.bewegung_bulk_delete, name="bewegung_bulk_delete"),
    path("bewegungen/<int:pk>/", views.bewegung_detail, name="bewegung_detail"),
    path("bewegungen/<int:pk>/loeschen/", views.bewegung_delete, name="bewegung_delete"),
]

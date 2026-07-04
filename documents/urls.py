from django.urls import path

from . import views

urlpatterns = [
    path("bewegung/<int:bewegung_id>/hochladen/", views.beleg_upload, name="beleg_upload"),
    path("<int:pk>/", views.beleg_download, name="beleg_download"),
    path("<int:pk>/loeschen/", views.beleg_delete, name="beleg_delete"),
]

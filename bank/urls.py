from django.urls import path

from . import views

urlpatterns = [
    path("import/", views.import_view, name="bewegung_import"),
    path("bewegungen/", views.bewegung_list, name="bewegung_list"),
    path("bewegungen/<int:pk>/", views.bewegung_detail, name="bewegung_detail"),
]

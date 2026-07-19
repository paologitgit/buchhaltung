from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("backup/", views.backup_list, name="backup_list"),
    path("backup/erstellen/", views.backup_create, name="backup_create"),
    path("backup/<str:filename>/herunterladen/", views.backup_download, name="backup_download"),
    path("backup/<str:filename>/wiederherstellen/", views.backup_restore, name="backup_restore"),
    path("backup/hochladen/", views.backup_upload, name="backup_upload"),
]

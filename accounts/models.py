from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        OWNER = "OWNER", "Inhaber:in"
        TRUSTEE = "TRUSTEE", "Treuhänder:in (nur Lesen)"

    role = models.CharField(max_length=10, choices=Role.choices, default=Role.OWNER)

    @property
    def is_trustee(self):
        return self.role == self.Role.TRUSTEE

    @property
    def is_owner(self):
        return self.role == self.Role.OWNER

    def has_write_access(self):
        return self.is_active and self.is_owner

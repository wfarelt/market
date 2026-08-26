from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models


class User(AbstractUser):
    """Custom user — extend here instead of patching AbstractUser later."""

    ROLE_SUPERADMIN = "superadmin"
    ROLE_ADMIN = "admin"
    ROLE_CAJERO = "cajero"
    ROLE_ALMACENERO = "almacenero"

    ROLE_CHOICES = [
        (ROLE_SUPERADMIN, "Superadministrador"),
        (ROLE_ADMIN, "Administrador"),
        (ROLE_CAJERO, "Cajero"),
        (ROLE_ALMACENERO, "Almacenero"),
    ]

    branch = models.ForeignKey(
        "branches.Branch",
        blank=True,
        null=True,
        on_delete=models.PROTECT,
        related_name="users",
        verbose_name="sucursal",
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default=ROLE_SUPERADMIN,
        verbose_name="rol",
    )

    class Meta:
        verbose_name = "user"
        verbose_name_plural = "users"

    def clean(self):
        super().clean()
        if self.role == self.ROLE_SUPERADMIN and self.branch_id:
            raise ValidationError({"branch": "Un superadministrador no puede tener sucursal asignada."})
        if self.role != self.ROLE_SUPERADMIN and not self.branch_id:
            raise ValidationError({"branch": "Este rol requiere una sucursal asignada."})


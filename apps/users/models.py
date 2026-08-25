from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Custom user — extend here instead of patching AbstractUser later."""

    class Meta:
        verbose_name = "user"
        verbose_name_plural = "users"


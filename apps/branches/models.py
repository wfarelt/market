from django.db import models

from apps.core.models import TimeStampedModel


class Branch(TimeStampedModel):

    name = models.CharField(max_length=100)
    # Short immutable identifier used across Kardex, reports, and transfers.
    code = models.CharField(max_length=20, unique=True)
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "branch"
        verbose_name_plural = "branches"

    def __str__(self):
        return f"{self.code} – {self.name}"

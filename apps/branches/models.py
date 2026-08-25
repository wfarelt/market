from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import TimeStampedModel


class Branch(TimeStampedModel):

    ROLE_ADMIN = "admin"
    ROLE_CASHIER = "cashier"
    ROLE_STOCK_MANAGER = "stock_manager"

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


class UserBranch(models.Model):

    ROLE_CHOICES = [
        (Branch.ROLE_ADMIN, "Admin"),
        (Branch.ROLE_CASHIER, "Cashier"),
        (Branch.ROLE_STOCK_MANAGER, "Stock Manager"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="user_branches",
    )
    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name="user_branches",
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    # Determines the branch pre-selected when the user logs in.
    is_default = models.BooleanField(default=False)

    class Meta:
        # One assignment per user+branch pair.
        unique_together = [("user", "branch")]
        verbose_name = "user branch"
        verbose_name_plural = "user branches"

    def __str__(self):
        return f"{self.user} @ {self.branch.code} ({self.role})"

    def clean(self):
        # Enforce a single default branch per user.
        if self.is_default:
            qs = UserBranch.objects.filter(user=self.user, is_default=True)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError(
                    {"is_default": "This user already has a default branch."}
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

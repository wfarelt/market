from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from apps.branches.models import Branch
from apps.core.models import TimeStampedModel
from apps.inventory.models import InventoryMovement
from apps.products.models import Product


class Transfer(TimeStampedModel):
	STATUS_DRAFT = "DRAFT"
	STATUS_SENT = "SENT"
	STATUS_RECEIVED = "RECEIVED"
	STATUS_CANCELLED = "CANCELLED"
	STATUS_CHOICES = [(STATUS_DRAFT, "Borrador"), (STATUS_SENT, "Enviado"), (STATUS_RECEIVED, "Recibido"), (STATUS_CANCELLED, "Cancelado")]

	number = models.CharField(max_length=20, unique=True, blank=True)
	origin_branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="outgoing_transfers", verbose_name="sucursal origen")
	destination_branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="incoming_transfers", verbose_name="sucursal destino")
	status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_DRAFT)
	notes = models.TextField(blank=True, verbose_name="observación")
	sent_at = models.DateTimeField(null=True, blank=True)
	received_at = models.DateTimeField(null=True, blank=True)
	cancelled_at = models.DateTimeField(null=True, blank=True)
	sent_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="sent_transfers")
	received_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="received_transfers")
	cancelled_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="cancelled_transfers")
	outgoing_movement = models.OneToOneField(InventoryMovement, null=True, blank=True, on_delete=models.PROTECT, related_name="outgoing_transfer")
	incoming_movement = models.OneToOneField(InventoryMovement, null=True, blank=True, on_delete=models.PROTECT, related_name="incoming_transfer")

	class Meta:
		ordering = ["-created_at"]
		constraints = [models.CheckConstraint(condition=~models.Q(origin_branch=models.F("destination_branch")), name="transfer_different_branches")]
		verbose_name = "traspaso"
		verbose_name_plural = "traspasos"

	def clean(self):
		super().clean()
		if self.origin_branch_id and self.origin_branch_id == self.destination_branch_id:
			raise ValidationError({"destination_branch": "La sucursal destino debe ser distinta a la origen."})

	def save(self, *args, **kwargs):
		is_new = self._state.adding and not self.number
		super().save(*args, **kwargs)
		if is_new:
			self.number = f"TRF-{self.pk:06d}"
			super().save(update_fields=["number"])

	def __str__(self):
		return self.number or f"Traspaso #{self.pk}"


class TransferItem(TimeStampedModel):
	transfer = models.ForeignKey(Transfer, on_delete=models.CASCADE, related_name="items")
	product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="transfer_items")
	requested_quantity = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(0.01)])
	sent_quantity = models.DecimalField(max_digits=15, decimal_places=2, default=0, validators=[MinValueValidator(0)])
	received_quantity = models.DecimalField(max_digits=15, decimal_places=2, default=0, validators=[MinValueValidator(0)])

	class Meta:
		constraints = [models.UniqueConstraint(fields=["transfer", "product"], name="unique_product_per_transfer")]
		verbose_name = "detalle de traspaso"
		verbose_name_plural = "detalles de traspaso"

	def clean(self):
		super().clean()
		if self.product_id and not self.product.is_active:
			raise ValidationError({"product": "El producto debe estar activo."})
		if self.sent_quantity > self.requested_quantity:
			raise ValidationError({"sent_quantity": "No puede superar la cantidad solicitada."})
		if self.received_quantity > self.sent_quantity:
			raise ValidationError({"received_quantity": "No puede superar la cantidad enviada."})


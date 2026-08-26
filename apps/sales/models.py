from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from apps.branches.models import Branch
from apps.cash.models import CashMovement, CashRegister
from apps.core.models import TimeStampedModel
from apps.inventory.models import InventoryMovement
from apps.products.models import Product


class Sale(TimeStampedModel):
	STATUS_DRAFT = "DRAFT"
	STATUS_COMPLETED = "COMPLETED"
	STATUS_CANCELLED = "CANCELLED"
	STATUS_CHOICES = [(STATUS_DRAFT, "Borrador"), (STATUS_COMPLETED, "Completada"), (STATUS_CANCELLED, "Anulada")]
	PAYMENT_CASH = "CASH"
	PAYMENT_QR = "QR"
	PAYMENT_CARD = "CARD"
	PAYMENT_TRANSFER = "TRANSFER"
	PAYMENT_CREDIT = "CREDIT"
	PAYMENT_CHOICES = [(PAYMENT_CASH, "Efectivo"), (PAYMENT_QR, "QR"), (PAYMENT_CARD, "Tarjeta"), (PAYMENT_TRANSFER, "Transferencia"), (PAYMENT_CREDIT, "Crédito")]

	number = models.CharField(max_length=20, unique=True, blank=True)
	branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="sales")
	user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="sales")
	cash_register = models.ForeignKey(CashRegister, on_delete=models.PROTECT, related_name="sales")
	status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_DRAFT)
	payment_method = models.CharField(max_length=20, choices=PAYMENT_CHOICES, default=PAYMENT_CASH)
	cash_received = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
	change_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
	subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
	discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
	total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
	inventory_movement = models.OneToOneField(InventoryMovement, null=True, blank=True, on_delete=models.PROTECT, related_name="sale")
	cash_movement = models.OneToOneField(CashMovement, null=True, blank=True, on_delete=models.PROTECT, related_name="sale")
	cancelled_inventory_movement = models.OneToOneField(InventoryMovement, null=True, blank=True, on_delete=models.PROTECT, related_name="cancelled_sale")
	cancelled_cash_movement = models.OneToOneField(CashMovement, null=True, blank=True, on_delete=models.PROTECT, related_name="cancelled_sale")
	completed_at = models.DateTimeField(null=True, blank=True)
	cancelled_at = models.DateTimeField(null=True, blank=True)
	notes = models.TextField(blank=True)

	class Meta:
		ordering = ["-created_at"]

	def save(self, *args, **kwargs):
		new = self._state.adding and not self.number
		super().save(*args, **kwargs)
		if new:
			self.number = f"V-{self.pk:06d}"
			super().save(update_fields=["number"])


class SaleItem(TimeStampedModel):
	sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="items")
	product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="sale_items")
	quantity = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(0.01)])
	unit_price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
	discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)])
	subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)

	class Meta:
		constraints = [models.UniqueConstraint(fields=["sale", "product"], name="unique_product_per_sale")]

	def clean(self):
		super().clean()
		if not self.product.is_active:
			raise ValidationError({"product": "El producto debe estar activo."})
		if self.discount_amount > self.unit_price * self.quantity:
			raise ValidationError({"discount_amount": "El descuento no puede superar el importe de la línea."})

	def save(self, *args, **kwargs):
		self.subtotal = self.unit_price * self.quantity - self.discount_amount
		super().save(*args, **kwargs)


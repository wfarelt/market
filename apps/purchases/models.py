from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.branches.models import Branch
from apps.core.models import TimeStampedModel
from apps.inventory.models import InventoryMovement
from apps.products.models import Product


class Supplier(TimeStampedModel):
	name = models.CharField(max_length=150, verbose_name="nombre")
	tax_id = models.CharField(max_length=20, blank=True, verbose_name="NIT")
	phone = models.CharField(max_length=20, blank=True, verbose_name="teléfono")
	email = models.EmailField(blank=True)
	address = models.TextField(blank=True, verbose_name="dirección")
	is_active = models.BooleanField(default=True, verbose_name="activo")

	class Meta:
		ordering = ["name"]
		verbose_name = "proveedor"
		verbose_name_plural = "proveedores"

	def __str__(self):
		return self.name


class Purchase(TimeStampedModel):
	STATUS_DRAFT = "DRAFT"
	STATUS_CONFIRMED = "CONFIRMED"
	STATUS_CANCELLED = "CANCELLED"
	STATUS_CHOICES = [
		(STATUS_DRAFT, "Borrador"),
		(STATUS_CONFIRMED, "Confirmada"),
		(STATUS_CANCELLED, "Anulada"),
	]

	number = models.CharField(max_length=20, unique=True, blank=True)
	branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="purchases")
	supplier = models.ForeignKey(Supplier, null=True, blank=True, on_delete=models.PROTECT, related_name="purchases", verbose_name="proveedor")
	purchase_date = models.DateField(default=timezone.localdate, verbose_name="fecha de compra")
	invoice_number = models.CharField(max_length=50, blank=True, verbose_name="número de factura")
	status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_DRAFT)
	discount = models.DecimalField(max_digits=12, decimal_places=2, default=0, blank=True, validators=[MinValueValidator(0)], verbose_name="descuento")
	notes = models.TextField(blank=True)
	inventory_movement = models.OneToOneField(InventoryMovement, null=True, blank=True, on_delete=models.PROTECT, related_name="purchase")
	confirmed_at = models.DateTimeField(null=True, blank=True)

	class Meta:
		ordering = ["-created_at"]
		verbose_name = "compra"
		verbose_name_plural = "compras"

	def __str__(self):
		return self.number

	def save(self, *args, **kwargs):
		new = self._state.adding and not self.number
		super().save(*args, **kwargs)
		if new:
			self.number = f"C-{self.pk:06d}"
			super().save(update_fields=["number"])


class PurchaseItem(TimeStampedModel):
	purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name="items")
	product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="purchase_items")
	quantity = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(0.01)])
	unit_cost = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
	sale_price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
	update_cost = models.BooleanField(default=False, verbose_name="actualizar costo")
	update_sale_price = models.BooleanField(default=False, verbose_name="actualizar precio de venta")

	class Meta:
		constraints = [models.UniqueConstraint(fields=["purchase", "product"], name="unique_product_per_purchase")]
		verbose_name = "línea de compra"
		verbose_name_plural = "líneas de compra"

	@property
	def subtotal(self):
		return self.quantity * self.unit_cost


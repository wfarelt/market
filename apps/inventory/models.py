from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from apps.branches.models import Branch
from apps.core.models import TimeStampedModel
from apps.products.models import Product


class Stock(TimeStampedModel):
	product = models.ForeignKey(
		Product,
		on_delete=models.PROTECT,
		related_name="stocks",
		verbose_name="producto",
	)
	branch = models.ForeignKey(
		Branch,
		on_delete=models.PROTECT,
		related_name="stocks",
		verbose_name="sucursal",
	)
	quantity = models.DecimalField(
		max_digits=15,
		decimal_places=2,
		default=0,
		validators=[MinValueValidator(0)],
		verbose_name="existencia",
	)

	class Meta:
		ordering = ["branch__name", "product__name"]
		constraints = [
			models.UniqueConstraint(
				fields=["product", "branch"],
				name="unique_stock_per_product_branch",
			),
		]
		verbose_name = "existencia"
		verbose_name_plural = "existencias"

	def __str__(self):
		return f"{self.product.sku} @ {self.branch.code}: {self.quantity}"


class InventoryMovement(TimeStampedModel):
	TYPE_ENTRY = "ENTRY"
	TYPE_OUTPUT = "OUTPUT"
	TYPE_TRANSFER = "TRANSFER"
	TYPE_ADJUSTMENT = "ADJUSTMENT"

	TYPE_CHOICES = [
		(TYPE_ENTRY, "Entrada"),
		(TYPE_OUTPUT, "Salida"),
		(TYPE_TRANSFER, "Traspaso"),
		(TYPE_ADJUSTMENT, "Ajuste"),
	]

	STATUS_DRAFT = "DRAFT"
	STATUS_POSTED = "POSTED"
	STATUS_CHOICES = [
		(STATUS_DRAFT, "Borrador"),
		(STATUS_POSTED, "Confirmado"),
	]

	movement_type = models.CharField(max_length=20, choices=TYPE_CHOICES, verbose_name="tipo")
	branch = models.ForeignKey(
		Branch,
		on_delete=models.PROTECT,
		related_name="inventory_movements",
		verbose_name="sucursal",
	)
	status = models.CharField(
		max_length=10,
		choices=STATUS_CHOICES,
		default=STATUS_DRAFT,
		verbose_name="estado",
	)
	notes = models.TextField(blank=True, verbose_name="notas")

	class Meta:
		ordering = ["-created_at"]
		indexes = [models.Index(fields=["branch", "-created_at"])]
		verbose_name = "movimiento de inventario"
		verbose_name_plural = "movimientos de inventario"

	def __str__(self):
		return f"{self.get_movement_type_display()} #{self.pk}"


class InventoryMovementLine(TimeStampedModel):
	ADJUSTMENT_ENTRY = "ENTRY"
	ADJUSTMENT_OUTPUT = "OUTPUT"
	ADJUSTMENT_DIRECTION_CHOICES = [
		(ADJUSTMENT_ENTRY, "Aumentar"),
		(ADJUSTMENT_OUTPUT, "Disminuir"),
	]

	movement = models.ForeignKey(
		InventoryMovement,
		on_delete=models.CASCADE,
		related_name="lines",
		verbose_name="movimiento",
	)
	product = models.ForeignKey(
		Product,
		on_delete=models.PROTECT,
		related_name="inventory_movement_lines",
		verbose_name="producto",
	)
	quantity = models.DecimalField(
		max_digits=15,
		decimal_places=2,
		validators=[MinValueValidator(0.01)],
		verbose_name="cantidad",
	)
	adjustment_direction = models.CharField(
		max_length=10,
		choices=ADJUSTMENT_DIRECTION_CHOICES,
		blank=True,
		verbose_name="dirección del ajuste",
	)

	class Meta:
		constraints = [
			models.UniqueConstraint(
				fields=["movement", "product"],
				name="unique_product_per_inventory_movement",
			),
		]
		verbose_name = "línea de movimiento"
		verbose_name_plural = "líneas de movimiento"

	def clean(self):
		super().clean()
		if not self.movement_id:
			return
		if self.movement.movement_type == InventoryMovement.TYPE_ADJUSTMENT:
			if not self.adjustment_direction:
				raise ValidationError({"adjustment_direction": "Indica si el ajuste aumenta o disminuye la existencia."})
		elif self.adjustment_direction:
			raise ValidationError({"adjustment_direction": "Solo se permite en movimientos de ajuste."})


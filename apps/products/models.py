from django.core.validators import MinValueValidator
from django.db import models

from apps.core.models import TimeStampedModel


class CatalogModel(TimeStampedModel):
	name = models.CharField(max_length=100)
	code = models.CharField(max_length=20, unique=True)
	description = models.TextField(blank=True)
	is_active = models.BooleanField(default=True)

	class Meta:
		abstract = True
		ordering = ["name"]

	def __str__(self):
		return f"{self.code} - {self.name}"


class Category(CatalogModel):
	class Meta:
		ordering = ["name"]
		verbose_name = "categoría"
		verbose_name_plural = "categorías"


class Brand(CatalogModel):
	class Meta:
		ordering = ["name"]
		verbose_name = "marca"
		verbose_name_plural = "marcas"


class UnitMeasure(CatalogModel):
	symbol = models.CharField(max_length=10, unique=True)

	class Meta:
		ordering = ["name"]
		verbose_name = "unidad de medida"
		verbose_name_plural = "unidades de medida"


class Product(TimeStampedModel):
	name = models.CharField(max_length=255)
	sku = models.CharField(max_length=50, unique=True)
	description = models.TextField(blank=True)
	category = models.ForeignKey(
		Category,
		blank=True,
		null=True,
		on_delete=models.PROTECT,
		related_name="products",
	)
	brand = models.ForeignKey(
		Brand,
		blank=True,
		null=True,
		on_delete=models.PROTECT,
		related_name="products",
	)
	unit_measure = models.ForeignKey(
		UnitMeasure,
		blank=True,
		null=True,
		on_delete=models.PROTECT,
		related_name="products",
		verbose_name="unidad de medida",
	)
	list_price = models.DecimalField(
		max_digits=12,
		decimal_places=2,
		default=0,
		validators=[MinValueValidator(0)],
		verbose_name="precio de lista",
	)
	cost_price = models.DecimalField(
		max_digits=12,
		decimal_places=2,
		default=0,
		validators=[MinValueValidator(0)],
		verbose_name="costo actual",
	)
	is_active = models.BooleanField(default=True)

	class Meta:
		ordering = ["name"]
		verbose_name = "producto"
		verbose_name_plural = "productos"

	def __str__(self):
		return f"{self.sku} - {self.name}"


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


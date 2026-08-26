from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from apps.branches.models import Branch
from apps.inventory.models import Stock
from apps.products.models import Product


class StockModelTests(TestCase):
	def setUp(self):
		self.product = Product.objects.create(name="Coca Cola", sku="COCA-600")
		self.central = Branch.objects.create(name="Central", code="CENTRAL")
		self.north = Branch.objects.create(name="Norte", code="NORTE")

	def test_stock_is_scoped_to_product_and_branch(self):
		central_stock = Stock.objects.create(
			product=self.product,
			branch=self.central,
			quantity=Decimal("100"),
		)
		north_stock = Stock.objects.create(
			product=self.product,
			branch=self.north,
			quantity=Decimal("25"),
		)

		self.assertEqual(central_stock.quantity, Decimal("100"))
		self.assertEqual(north_stock.quantity, Decimal("25"))

	def test_product_branch_pair_must_be_unique(self):
		Stock.objects.create(product=self.product, branch=self.central, quantity=1)

		with self.assertRaises(IntegrityError):
			Stock.objects.create(product=self.product, branch=self.central, quantity=2)

	def test_quantity_cannot_be_negative(self):
		stock = Stock(product=self.product, branch=self.central, quantity=-1)

		with self.assertRaises(ValidationError):
			stock.full_clean()


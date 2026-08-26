from decimal import Decimal

from django.test import TestCase

from apps.products.models import Brand, Category, Product, UnitMeasure


class ProductModelTests(TestCase):
	def test_product_is_a_catalog_item_without_stock(self):
		category = Category.objects.create(name="Bebidas", code="BEB")
		brand = Brand.objects.create(name="Agua Clara", code="AC")
		unit_measure = UnitMeasure.objects.create(name="Unidad", code="UND", symbol="u")
		product = Product.objects.create(
			name="Agua 600 ml",
			sku="AGUA-600",
			category=category,
			brand=brand,
			unit_measure=unit_measure,
			list_price=Decimal("12.50"),
		)

		self.assertEqual(product.category, category)
		self.assertEqual(product.list_price, Decimal("12.50"))
		self.assertNotIn("stock", [field.name for field in Product._meta.fields])


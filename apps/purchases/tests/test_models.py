from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.branches.models import Branch
from apps.inventory.models import Stock
from apps.products.models import Product
from apps.purchases.models import Purchase, PurchaseItem
from apps.purchases.services import confirm_purchase
from apps.users.models import User


class PurchaseServiceTests(TestCase):
	def setUp(self):
		self.branch = Branch.objects.create(name="Central", code="CENTRAL")
		self.user = User.objects.create_user(
			username="admin",
			password="test-password",
			branch=self.branch,
			role=User.ROLE_ADMIN,
		)
		self.product = Product.objects.create(
			name="Producto prueba",
			sku="PURCHASE-001",
			cost_price=Decimal("10.00"),
			list_price=Decimal("20.00"),
		)

	def create_purchase(self, *, update_cost=False, update_sale_price=False):
		purchase = Purchase.objects.create(branch=self.branch, created_by=self.user)
		PurchaseItem.objects.create(
			purchase=purchase,
			product=self.product,
			quantity=Decimal("5.00"),
			unit_cost=Decimal("12.00"),
			sale_price=Decimal("25.00"),
			update_cost=update_cost,
			update_sale_price=update_sale_price,
			created_by=self.user,
		)
		return purchase

	def test_confirmed_purchase_increases_stock_without_changing_prices_by_default(self):
		purchase = self.create_purchase()

		confirm_purchase(purchase=purchase, user=self.user)

		self.product.refresh_from_db()
		purchase.refresh_from_db()
		stock = Stock.objects.get(branch=self.branch, product=self.product)
		self.assertEqual(stock.quantity, Decimal("5.00"))
		self.assertEqual(self.product.cost_price, Decimal("10.00"))
		self.assertEqual(self.product.list_price, Decimal("20.00"))
		self.assertEqual(purchase.status, Purchase.STATUS_CONFIRMED)
		self.assertIsNotNone(purchase.inventory_movement)

	def test_confirmed_purchase_updates_only_selected_prices(self):
		purchase = self.create_purchase(update_cost=True, update_sale_price=True)

		confirm_purchase(purchase=purchase, user=self.user)

		self.product.refresh_from_db()
		self.assertEqual(self.product.cost_price, Decimal("12.00"))
		self.assertEqual(self.product.list_price, Decimal("25.00"))

	def test_confirmed_purchase_cannot_be_confirmed_twice(self):
		purchase = self.create_purchase()
		confirm_purchase(purchase=purchase, user=self.user)

		with self.assertRaises(ValidationError):
			confirm_purchase(purchase=purchase, user=self.user)


from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse

from apps.branches.models import Branch
from apps.inventory.models import InventoryMovement, InventoryMovementLine, Stock
from apps.inventory.services import post_inventory_movement
from apps.products.models import Product
from apps.users.models import User


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


class InventoryMovementServiceTests(TestCase):
	def setUp(self):
		self.product = Product.objects.create(name="Coca Cola", sku="COCA-600")
		self.branch = Branch.objects.create(name="Central", code="CENTRAL")

	def test_entry_increases_stock_and_posts_movement(self):
		movement = InventoryMovement.objects.create(
			movement_type=InventoryMovement.TYPE_ENTRY,
			branch=self.branch,
		)
		InventoryMovementLine.objects.create(
			movement=movement,
			product=self.product,
			quantity=Decimal("100"),
		)

		post_inventory_movement(movement)

		self.assertEqual(Stock.objects.get(product=self.product, branch=self.branch).quantity, Decimal("100"))
		self.assertEqual(InventoryMovement.objects.get(pk=movement.pk).status, InventoryMovement.STATUS_POSTED)

	def test_output_rejects_insufficient_stock(self):
		Stock.objects.create(product=self.product, branch=self.branch, quantity=Decimal("5"))
		movement = InventoryMovement.objects.create(
			movement_type=InventoryMovement.TYPE_OUTPUT,
			branch=self.branch,
		)
		InventoryMovementLine.objects.create(
			movement=movement,
			product=self.product,
			quantity=Decimal("6"),
		)

		with self.assertRaises(ValidationError):
			post_inventory_movement(movement)

		self.assertEqual(Stock.objects.get(product=self.product, branch=self.branch).quantity, Decimal("5"))

	def test_negative_adjustment_decreases_stock(self):
		Stock.objects.create(product=self.product, branch=self.branch, quantity=Decimal("10"))
		movement = InventoryMovement.objects.create(
			movement_type=InventoryMovement.TYPE_ADJUSTMENT,
			branch=self.branch,
		)
		InventoryMovementLine.objects.create(
			movement=movement,
			product=self.product,
			quantity=Decimal("3"),
			adjustment_direction=InventoryMovementLine.ADJUSTMENT_OUTPUT,
		)

		post_inventory_movement(movement)

		self.assertEqual(Stock.objects.get(product=self.product, branch=self.branch).quantity, Decimal("7"))

	def test_admin_can_create_and_confirm_a_movement(self):
		admin = User.objects.create_user(
			username="admin",
			password="test-password",
			branch=self.branch,
			role=User.ROLE_ADMIN,
		)
		self.client.force_login(admin)
		response = self.client.post(
			reverse("inventory:movement-create"),
			{
				"movement_type": InventoryMovement.TYPE_ENTRY,
				"branch": self.branch.pk,
				"notes": "Inventario inicial",
				"lines-TOTAL_FORMS": "1",
				"lines-INITIAL_FORMS": "0",
				"lines-MIN_NUM_FORMS": "0",
				"lines-MAX_NUM_FORMS": "1000",
				"lines-0-product": self.product.pk,
				"lines-0-quantity": "12",
				"lines-0-adjustment_direction": "",
			},
		)

		movement = InventoryMovement.objects.get()
		self.assertRedirects(response, reverse("inventory:movement-detail", args=[movement.pk]))
		self.client.post(reverse("inventory:movement-post", args=[movement.pk]))
		self.assertEqual(Stock.objects.get(product=self.product, branch=self.branch).quantity, Decimal("12"))


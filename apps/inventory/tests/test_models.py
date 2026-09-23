from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse

from apps.branches.models import Branch
from apps.inventory.models import InventoryMovement, InventoryMovementLine, Stock
from apps.inventory.forms import InventoryMovementFilterForm, StockInitialForm
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

	def test_initial_stock_form_requires_an_integer_quantity(self):
		form = StockInitialForm(
			data={"product": self.product.pk, "branch": self.central.pk, "quantity": "2.5"}
		)

		self.assertFalse(form.is_valid())
		self.assertIn("quantity", form.errors)

	def test_stock_list_filters_by_branch(self):
		central_stock = Stock.objects.create(product=self.product, branch=self.central, quantity=10)
		Stock.objects.create(product=self.product, branch=self.north, quantity=20)
		admin = User.objects.create_user(
			username="admin",
			password="test-password",
			branch=self.central,
			role=User.ROLE_ADMIN,
		)
		self.client.force_login(admin)

		response = self.client.get(reverse("inventory:list"), {"branch": self.central.pk})

		self.assertEqual(list(response.context["stocks"]), [central_stock])


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


class InventoryMovementFilterTests(TestCase):
	def setUp(self):
		self.branch = Branch.objects.create(name="Central", code="CENTRAL")
		self.other_branch = Branch.objects.create(name="Norte", code="NORTE")
		self.admin = User.objects.create_user(
			username="admin",
			password="test-password",
			branch=self.branch,
			role=User.ROLE_ADMIN,
		)
		self.client.force_login(self.admin)
		self.matching_movement = InventoryMovement.objects.create(
			movement_type=InventoryMovement.TYPE_ENTRY,
			movement_date=date(2026, 9, 10),
			branch=self.branch,
			status=InventoryMovement.STATUS_POSTED,
			notes="Recepción proveedor",
		)
		InventoryMovement.objects.create(
			movement_type=InventoryMovement.TYPE_OUTPUT,
			movement_date=date(2026, 9, 20),
			branch=self.other_branch,
			notes="Salida dañados",
		)

	def test_list_applies_combined_filters(self):
		response = self.client.get(
			reverse("inventory:movement-list"),
			{
				"start_date": "2026-09-01",
				"end_date": "2026-09-15",
				"movement_type": InventoryMovement.TYPE_ENTRY,
				"branch": self.branch.pk,
				"status": InventoryMovement.STATUS_POSTED,
			},
		)

		self.assertEqual(list(response.context["movements"]), [self.matching_movement])

	def test_list_searches_notes_and_rejects_invalid_date_range(self):
		response = self.client.get(reverse("inventory:movement-list"), {"q": "dañados"})
		self.assertEqual(response.context["movements"].count(), 1)
		self.assertEqual(response.context["movements"].first().branch, self.other_branch)

		filter_form = InventoryMovementFilterForm({"start_date": "2026-09-20", "end_date": "2026-09-01"})
		self.assertFalse(filter_form.is_valid())


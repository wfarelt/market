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
from apps.products.models import Category, Product
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
			location="Pasillo 1, estante A",
		)
		north_stock = Stock.objects.create(
			product=self.product,
			branch=self.north,
			quantity=Decimal("25"),
			location="Pasillo 3",
		)

		self.assertEqual(central_stock.quantity, Decimal("100"))
		self.assertEqual(north_stock.quantity, Decimal("25"))
		self.assertEqual(central_stock.location, "Pasillo 1, estante A")
		self.assertEqual(north_stock.location, "Pasillo 3")

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
			data={"product": self.product.pk, "branch": self.central.pk, "quantity": "2.5", "location": "Pasillo 1"}
		)

		self.assertFalse(form.is_valid())
		self.assertIn("quantity", form.errors)

	def test_initial_stock_duplicate_shows_explanation_and_preserves_existing_stock(self):
		Stock.objects.create(product=self.product, branch=self.central, quantity=10)
		admin = User.objects.create_user(
			username="admin",
			password="test-password",
			branch=self.central,
			role=User.ROLE_ADMIN,
		)
		self.client.force_login(admin)

		response = self.client.post(
			reverse("inventory:create"),
			{
				"product": self.product.pk,
				"branch": self.central.pk,
				"quantity": "20",
				"location": "Pasillo 1",
			},
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Ya existe una existencia para este producto")
		self.assertEqual(Stock.objects.count(), 1)
		self.assertEqual(Stock.objects.get().quantity, 10)

	def test_admin_can_update_stock_location_without_changing_quantity(self):
		stock = Stock.objects.create(product=self.product, branch=self.central, quantity=12)
		admin = User.objects.create_user(
			username="admin",
			password="test-password",
			branch=self.central,
			role=User.ROLE_ADMIN,
		)
		self.client.force_login(admin)

		response = self.client.post(
			reverse("inventory:stock-location-update", args=[stock.pk]),
			{"location": "Pasillo 2, estante B4"},
		)

		self.assertRedirects(response, reverse("inventory:list"))
		stock.refresh_from_db()
		self.assertEqual(stock.location, "Pasillo 2, estante B4")
		self.assertEqual(stock.quantity, 12)

	def test_warehouse_user_cannot_update_location_in_another_branch(self):
		stock = Stock.objects.create(product=self.product, branch=self.central, quantity=12)
		warehouse_user = User.objects.create_user(
			username="warehouse",
			password="test-password",
			branch=self.north,
			role=User.ROLE_ALMACENERO,
		)
		self.client.force_login(warehouse_user)

		response = self.client.post(
			reverse("inventory:stock-location-update", args=[stock.pk]),
			{"location": "Pasillo 2, estante B4"},
		)

		self.assertEqual(response.status_code, 404)
		stock.refresh_from_db()
		self.assertEqual(stock.location, "")

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

	def test_stock_list_defaults_to_users_branch_on_initial_load(self):
		central_stock = Stock.objects.create(product=self.product, branch=self.central, quantity=10)
		Stock.objects.create(product=self.product, branch=self.north, quantity=20)
		admin = User.objects.create_user(
			username="admin-default-branch",
			password="test-password",
			branch=self.central,
			role=User.ROLE_ADMIN,
		)
		self.client.force_login(admin)

		response = self.client.get(reverse("inventory:list"))

		self.assertEqual(list(response.context["stocks"]), [central_stock])
		self.assertEqual(response.context["filter_form"].cleaned_data["branch"], self.central)

	def test_stock_list_can_filter_to_positive_stock(self):
		in_stock = Stock.objects.create(product=self.product, branch=self.central, quantity=10)
		zero_stock_product = Product.objects.create(name="Jugo", sku="JUGO-1")
		Stock.objects.create(product=zero_stock_product, branch=self.central, quantity=0)
		admin = User.objects.create_user(
			username="admin-positive-stock",
			password="test-password",
			branch=self.central,
			role=User.ROLE_ADMIN,
		)
		self.client.force_login(admin)

		response = self.client.get(reverse("inventory:list"), {"with_stock": "on"})

		self.assertEqual(list(response.context["stocks"]), [in_stock])

	def test_stock_list_searches_by_product_sku_or_name(self):
		matching_sku = Stock.objects.create(product=self.product, branch=self.central, quantity=10)
		name_product = Product.objects.create(name="Agua mineral", sku="AGUA-1")
		matching_name = Stock.objects.create(product=name_product, branch=self.central, quantity=8)
		Product.objects.create(name="Leche", sku="LECHE-1")
		admin = User.objects.create_user(
			username="admin-product-search",
			password="test-password",
			branch=self.central,
			role=User.ROLE_ADMIN,
		)
		self.client.force_login(admin)

		for query, expected in [("COCA-6", matching_sku), ("mineral", matching_name)]:
			with self.subTest(query=query):
				response = self.client.get(reverse("inventory:list"), {"q": query})
				self.assertEqual(list(response.context["stocks"]), [expected])

	def test_stock_list_filters_by_category_and_combines_with_product_search(self):
		beverages = Category.objects.create(name="Bebidas", code="BEBIDAS")
		cleaning = Category.objects.create(name="Limpieza", code="LIMPIEZA")
		self.product.category = beverages
		self.product.save()
		matching_stock = Stock.objects.create(product=self.product, branch=self.central, quantity=10)
		other_product = Product.objects.create(
			name="Coca Cola botella grande", sku="COCA-2", category=cleaning
		)
		Stock.objects.create(product=other_product, branch=self.central, quantity=7)
		admin = User.objects.create_user(
			username="admin-category-filter",
			password="test-password",
			branch=self.central,
			role=User.ROLE_ADMIN,
		)
		self.client.force_login(admin)

		response = self.client.get(
			reverse("inventory:list"),
			{"category": beverages.pk, "q": "COCA"},
		)

		self.assertEqual(list(response.context["stocks"]), [matching_stock])
		self.assertContains(response, "Bebidas")

	def test_cashier_sees_only_own_branch_inventory_even_if_other_branch_is_requested(self):
		own_stock = Stock.objects.create(product=self.product, branch=self.central, quantity=10)
		Stock.objects.create(product=self.product, branch=self.north, quantity=20)
		cashier = User.objects.create_user(
			username="cashier-stock-list",
			password="test-password",
			branch=self.central,
			role=User.ROLE_CAJERO,
		)
		self.client.force_login(cashier)

		response = self.client.get(reverse("inventory:list"), {"branch": self.north.pk})

		self.assertEqual(response.status_code, 200)
		self.assertEqual(list(response.context["stocks"]), [own_stock])
		self.assertContains(response, reverse("inventory:stock-location-update", args=[own_stock.pk]))
		self.assertNotContains(response, reverse("inventory:create"))
		self.assertNotContains(response, "Todas las sucursales")

	def test_cashier_cannot_access_inventory_write_and_movement_routes(self):
		cashier = User.objects.create_user(
			username="cashier-restricted-routes",
			password="test-password",
			branch=self.central,
			role=User.ROLE_CAJERO,
		)
		self.client.force_login(cashier)

		for url in [
			reverse("inventory:create"),
			reverse("inventory:movement-list"),
			reverse("inventory:movement-create"),
		]:
			with self.subTest(url=url):
				self.assertEqual(self.client.get(url).status_code, 403)

	def test_cashier_can_update_location_only_in_own_branch(self):
		own_stock = Stock.objects.create(product=self.product, branch=self.central, quantity=12)
		other_product = Product.objects.create(name="Jugo", sku="JUGO-1")
		other_stock = Stock.objects.create(product=other_product, branch=self.north, quantity=5)
		cashier = User.objects.create_user(
			username="cashier-location",
			password="test-password",
			branch=self.central,
			role=User.ROLE_CAJERO,
		)
		self.client.force_login(cashier)

		response = self.client.post(
			reverse("inventory:stock-location-update", args=[own_stock.pk]),
			{"location": "Pasillo 4, estante C"},
		)
		self.assertRedirects(response, reverse("inventory:list"))
		own_stock.refresh_from_db()
		self.assertEqual(own_stock.location, "Pasillo 4, estante C")
		self.assertEqual(own_stock.quantity, 12)

		response = self.client.post(
			reverse("inventory:stock-location-update", args=[other_stock.pk]),
			{"location": "No autorizada"},
		)
		self.assertEqual(response.status_code, 404)


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


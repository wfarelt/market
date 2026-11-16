from datetime import timedelta
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.branches.models import Branch
from apps.inventory.models import InventoryMovement, Stock
from apps.inventory.services import create_initial_stock
from apps.products.models import Product
from apps.settings_app.models import BusinessDateSettings
from apps.users.models import User


class InitialStockTests(TestCase):
	def setUp(self):
		self.branch = Branch.objects.create(name="Central", code="CENTRAL")
		self.user = User.objects.create_user(username="admin", role=User.ROLE_ADMIN, branch=self.branch)
		self.product = Product.objects.create(name="Producto", sku="PROD")
		self.client.force_login(self.user)
		self.url = reverse("inventory:create")

	def test_positive_stock_creates_one_posted_entry_in_automatic_mode(self):
		before = timezone.now()
		response = self.client.post(self.url, {"product": self.product.pk, "branch": self.branch.pk, "quantity": "7"})
		after = timezone.now()
		self.assertRedirects(response, reverse("inventory:list"))
		stock = Stock.objects.get(product=self.product, branch=self.branch)
		self.assertEqual(stock.quantity, 7)
		movement = InventoryMovement.objects.get()
		self.assertEqual(movement.movement_type, InventoryMovement.TYPE_ENTRY)
		self.assertEqual(movement.status, InventoryMovement.STATUS_POSTED)
		self.assertEqual(movement.movement_date, timezone.localdate())
		self.assertLessEqual(before, movement.posted_at)
		self.assertLessEqual(movement.posted_at, after)
		self.assertEqual(movement.created_by, self.user)
		self.assertEqual(movement.notes, "Existencia inicial")
		line = movement.lines.get()
		self.assertEqual(line.product, self.product)
		self.assertEqual(line.quantity, 7)
		self.assertEqual(line.created_by, self.user)

	def test_historical_stock_uses_business_date_and_real_confirmation(self):
		historical = timezone.localdate() - timedelta(days=4)
		BusinessDateSettings.objects.filter(pk=1).update(mode=BusinessDateSettings.MODE_HISTORICAL, business_date=historical)
		before = timezone.now()
		response = self.client.post(self.url, {"product": self.product.pk, "branch": self.branch.pk, "quantity": "3"})
		after = timezone.now()
		self.assertRedirects(response, reverse("inventory:list"))
		movement = InventoryMovement.objects.get()
		self.assertEqual(movement.movement_date, historical)
		self.assertLessEqual(before, movement.posted_at)
		self.assertLessEqual(movement.posted_at, after)
		self.assertEqual(Stock.objects.get().quantity, 3)

	def test_zero_creates_stock_without_movement(self):
		response = self.client.post(self.url, {"product": self.product.pk, "branch": self.branch.pk, "quantity": "0"})
		self.assertRedirects(response, reverse("inventory:list"))
		self.assertEqual(Stock.objects.get().quantity, 0)
		self.assertFalse(InventoryMovement.objects.exists())

	def test_existing_stock_is_not_changed_or_backfilled(self):
		stock = Stock.objects.create(product=self.product, branch=self.branch, quantity=10)
		response = self.client.post(self.url, {"product": self.product.pk, "branch": self.branch.pk, "quantity": "7"})
		self.assertEqual(response.status_code, 200)
		self.assertTrue(response.context["form"].errors)
		with self.assertRaisesMessage(ValidationError, "Ya existe una existencia"):
			create_initial_stock(product=self.product, branch=self.branch, quantity=7, user=self.user)
		stock.refresh_from_db()
		self.assertEqual(stock.quantity, 10)
		self.assertFalse(InventoryMovement.objects.exists())

	def test_failure_posting_rolls_back_stock_and_movement(self):
		with patch("apps.inventory.services.post_inventory_movement", side_effect=ValidationError("No se pudo confirmar.")):
			response = self.client.post(self.url, {"product": self.product.pk, "branch": self.branch.pk, "quantity": "4"})
		self.assertContains(response, "No se pudo confirmar.")
		self.assertFalse(Stock.objects.exists())
		self.assertFalse(InventoryMovement.objects.exists())

	def test_invalid_quantity_leaves_no_stock_or_movement(self):
		for quantity in ("-1", "1.5"):
			with self.subTest(quantity=quantity):
				response = self.client.post(self.url, {"product": self.product.pk, "branch": self.branch.pk, "quantity": quantity})
				self.assertEqual(response.status_code, 200)
				self.assertTrue(response.context["form"].errors)
				self.assertFalse(Stock.objects.exists())
				self.assertFalse(InventoryMovement.objects.exists())

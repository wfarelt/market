from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from apps.branches.models import Branch
from apps.inventory.models import InventoryMovement, InventoryMovementLine, Stock
from apps.inventory.services import post_inventory_movement
from apps.products.models import Product
from apps.settings_app.models import BusinessDateSettings
from apps.users.models import User


class InventoryBusinessDateTests(TestCase):
	def setUp(self):
		self.branch = Branch.objects.create(name="Central", code="CENTRAL")
		self.user = User.objects.create_user(username="admin", role=User.ROLE_ADMIN, branch=self.branch)
		self.product = Product.objects.create(name="Producto", sku="PRODUCTO")
		self.historical_date = timezone.localdate() - timedelta(days=4)

	def enable_historical(self):
		BusinessDateSettings.objects.filter(pk=1).update(
			mode=BusinessDateSettings.MODE_HISTORICAL, business_date=self.historical_date,
		)

	def create_movement(self, movement_date, movement_type=InventoryMovement.TYPE_ENTRY, quantity=3, direction=""):
		movement = InventoryMovement.objects.create(
			movement_type=movement_type, movement_date=movement_date,
			branch=self.branch, created_by=self.user,
		)
		InventoryMovementLine.objects.create(
			movement=movement, product=self.product, quantity=quantity, adjustment_direction=direction,
		)
		return movement

	def test_historical_confirmation_records_real_time_and_stock(self):
		self.enable_historical()
		movement = self.create_movement(self.historical_date)
		before = timezone.now()
		post_inventory_movement(movement)
		after = timezone.now()
		movement.refresh_from_db()
		self.assertEqual(movement.movement_date, self.historical_date)
		self.assertEqual(movement.status, InventoryMovement.STATUS_POSTED)
		self.assertLessEqual(before, movement.posted_at)
		self.assertLessEqual(movement.posted_at, after)
		self.assertEqual(Stock.objects.get(branch=self.branch, product=self.product).quantity, 3)
		with self.assertRaisesMessage(ValidationError, "El movimiento ya fue confirmado"):
			post_inventory_movement(movement)
		self.assertEqual(Stock.objects.get(branch=self.branch, product=self.product).quantity, 3)
		self.client.force_login(self.user)
		response = self.client.get(reverse("inventory:movement-detail", args=[movement.pk]))
		self.assertContains(response, self.historical_date.strftime("%d/%m/%Y"))
		self.assertContains(response, timezone.localtime(movement.posted_at).strftime("%d/%m/%Y %H:%M"))
		self.assertContains(response, "Registro real")
		self.assertContains(response, "Confirmación real")

	def test_mismatched_date_is_rejected_without_stock_changes_then_can_be_corrected(self):
		self.enable_historical()
		movement = self.create_movement(self.historical_date - timedelta(days=1))
		with self.assertRaisesMessage(ValidationError, "La fecha del movimiento debe coincidir con la fecha de trabajo"):
			post_inventory_movement(movement)
		movement.refresh_from_db()
		self.assertEqual(movement.status, InventoryMovement.STATUS_DRAFT)
		self.assertIsNone(movement.posted_at)
		self.assertFalse(Stock.objects.exists())
		movement.movement_date = self.historical_date
		movement.save(update_fields=["movement_date"])
		post_inventory_movement(movement)
		self.assertEqual(Stock.objects.get(branch=self.branch, product=self.product).quantity, 3)

	def test_historical_insufficient_stock_rolls_back_adjustment(self):
		self.enable_historical()
		stock = Stock.objects.create(branch=self.branch, product=self.product, quantity=2)
		movement = self.create_movement(
			self.historical_date, InventoryMovement.TYPE_ADJUSTMENT, 3, InventoryMovementLine.ADJUSTMENT_OUTPUT,
		)
		with self.assertRaisesMessage(ValidationError, "Existencia insuficiente"):
			post_inventory_movement(movement)
		stock.refresh_from_db()
		movement.refresh_from_db()
		self.assertEqual(stock.quantity, 2)
		self.assertEqual(movement.status, InventoryMovement.STATUS_DRAFT)
		self.assertIsNone(movement.posted_at)

	def test_automatic_mode_allows_other_movement_dates(self):
		movement = self.create_movement(self.historical_date)
		post_inventory_movement(movement)
		movement.refresh_from_db()
		self.assertEqual(movement.movement_date, self.historical_date)
		self.assertIsNotNone(movement.posted_at)

	def test_historical_form_defaults_date_and_existing_draft_keeps_its_date(self):
		self.enable_historical()
		self.client.force_login(self.user)
		response = self.client.get(reverse("inventory:movement-create"))
		self.assertContains(response, self.historical_date.isoformat())
		self.assertContains(response, "la fecha del movimiento debe coincidir con la fecha de trabajo")
		movement = self.create_movement(self.historical_date - timedelta(days=1))
		response = self.client.get(reverse("inventory:movement-update", args=[movement.pk]))
		self.assertContains(response, (self.historical_date - timedelta(days=1)).isoformat())
		response = self.client.post(reverse("inventory:movement-post", args=[movement.pk]), follow=True)
		self.assertContains(response, "La fecha del movimiento debe coincidir con la fecha de trabajo")
		self.assertContains(response, "Confirmación real")
		self.assertContains(response, "No disponible")
		self.assertFalse(Stock.objects.exists())

	def test_historical_web_creation_without_date_uses_work_date(self):
		self.enable_historical()
		self.client.force_login(self.user)
		response = self.client.post(reverse("inventory:movement-create"), {
			"movement_date": "",
			"movement_type": InventoryMovement.TYPE_ENTRY,
			"branch": self.branch.pk,
			"lines-TOTAL_FORMS": "1",
			"lines-INITIAL_FORMS": "0",
			"lines-MIN_NUM_FORMS": "0",
			"lines-MAX_NUM_FORMS": "1000",
			"lines-0-product": self.product.pk,
			"lines-0-quantity": "3",
			"lines-0-adjustment_direction": "",
		})
		movement = InventoryMovement.objects.get()
		self.assertRedirects(response, reverse("inventory:movement-detail", args=[movement.pk]))
		self.assertEqual(movement.movement_date, self.historical_date)
		response = self.client.post(reverse("inventory:movement-post", args=[movement.pk]))
		self.assertRedirects(response, reverse("inventory:movement-detail", args=[movement.pk]))
		movement.refresh_from_db()
		self.assertIsNotNone(movement.posted_at)
		self.assertEqual(Stock.objects.get(branch=self.branch, product=self.product).quantity, 3)


class InventoryBusinessDateMigrationTests(TransactionTestCase):
	def test_existing_movement_keeps_original_date_and_unknown_confirmation(self):
		executor = MigrationExecutor(connection)
		latest_targets = executor.loader.graph.leaf_nodes()
		old_target = [("inventory", "0006_stock_location")]
		try:
			executor.migrate(old_target)
			old_apps = executor.loader.project_state(old_target).apps
			branch = old_apps.get_model("branches", "Branch").objects.create(name="Antigua", code="OLD")
			movement_date = timezone.localdate() - timedelta(days=5)
			movement = old_apps.get_model("inventory", "InventoryMovement").objects.create(
				branch=branch, movement_type="ENTRY", status="POSTED", movement_date=movement_date,
			)
			created_at = movement.created_at
			executor = MigrationExecutor(connection)
			executor.migrate(latest_targets)
			new_apps = executor.loader.project_state(latest_targets).apps
			migrated = new_apps.get_model("inventory", "InventoryMovement").objects.get(pk=movement.pk)
			self.assertEqual(migrated.movement_date, movement_date)
			self.assertEqual(migrated.created_at, created_at)
			self.assertEqual(migrated.status, "POSTED")
			self.assertIsNone(migrated.posted_at)
		finally:
			MigrationExecutor(connection).migrate(latest_targets)

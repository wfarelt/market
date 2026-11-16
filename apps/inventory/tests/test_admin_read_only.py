from django.test import TestCase
from django.urls import reverse

from apps.branches.models import Branch
from apps.inventory.models import InventoryMovement, InventoryMovementLine, Stock
from apps.inventory.services import post_inventory_movement
from apps.products.models import Product
from apps.users.models import User


class InventoryAdminReadOnlyTests(TestCase):
	def setUp(self):
		self.branch = Branch.objects.create(name="Central", code="CENTRAL")
		self.product = Product.objects.create(name="Producto", sku="PROD")
		self.admin = User.objects.create_superuser(username="admin", password="test-password")
		self.movement = InventoryMovement.objects.create(
			movement_type=InventoryMovement.TYPE_ENTRY, branch=self.branch, created_by=self.admin,
		)
		self.line = InventoryMovementLine.objects.create(movement=self.movement, product=self.product, quantity=5)
		post_inventory_movement(self.movement)
		self.movement.refresh_from_db()
		self.stock = Stock.objects.get(product=self.product, branch=self.branch)
		self.client.force_login(self.admin)

	def test_admin_allows_view_but_rejects_direct_writes(self):
		for model, obj in (("stock", self.stock), ("inventorymovement", self.movement)):
			with self.subTest(model=model):
				change_url = reverse(f"admin:inventory_{model}_change", args=[obj.pk])
				add_url = reverse(f"admin:inventory_{model}_add")
				delete_url = reverse(f"admin:inventory_{model}_delete", args=[obj.pk])
				self.assertEqual(self.client.get(change_url).status_code, 200)
				self.assertEqual(self.client.post(change_url, {"_save": "Save"}).status_code, 403)
				self.assertEqual(self.client.get(add_url).status_code, 403)
				self.assertEqual(self.client.post(add_url, {"_save": "Save"}).status_code, 403)
				self.assertEqual(self.client.get(delete_url).status_code, 403)
				self.assertEqual(self.client.post(delete_url, {"post": "yes"}).status_code, 403)
		self.stock.refresh_from_db()
		self.movement.refresh_from_db()
		self.assertEqual(self.stock.quantity, 5)
		self.assertEqual(self.movement.status, InventoryMovement.STATUS_POSTED)
		self.assertEqual(self.movement.lines.count(), 1)

	def test_lines_are_visible_but_cannot_be_edited_or_added(self):
		url = reverse("admin:inventory_inventorymovement_change", args=[self.movement.pk])
		response = self.client.get(url)
		self.assertContains(response, "PROD - Producto")
		self.assertNotContains(response, 'name="lines-0-quantity"')
		self.assertNotContains(response, "Añadir otro")
		response = self.client.post(url, {
			"lines-TOTAL_FORMS": "1", "lines-INITIAL_FORMS": "1",
			"lines-0-id": self.line.pk, "lines-0-quantity": "99", "_save": "Save",
		})
		self.assertEqual(response.status_code, 403)
		self.line.refresh_from_db()
		self.assertEqual(self.line.quantity, 5)

	def test_bulk_delete_is_unavailable_for_stock_and_movements(self):
		for model, obj in (("stock", self.stock), ("inventorymovement", self.movement)):
			with self.subTest(model=model):
				response = self.client.post(reverse(f"admin:inventory_{model}_changelist"), {
					"action": "delete_selected", "_selected_action": [obj.pk], "post": "yes",
				})
				self.assertEqual(response.status_code, 200)
		self.assertTrue(Stock.objects.filter(pk=self.stock.pk).exists())
		self.assertTrue(InventoryMovement.objects.filter(pk=self.movement.pk).exists())
		self.assertTrue(InventoryMovementLine.objects.filter(pk=self.line.pk).exists())

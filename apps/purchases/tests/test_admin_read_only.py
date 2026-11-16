from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from apps.branches.models import Branch
from apps.inventory.models import Stock
from apps.products.models import Product
from apps.purchases.models import Purchase, PurchaseItem, Supplier
from apps.purchases.services import confirm_purchase
from apps.users.models import User


class PurchaseAdminReadOnlyTests(TestCase):
	def setUp(self):
		self.branch = Branch.objects.create(name="Central", code="CENTRAL")
		self.operator = User.objects.create_user(username="operador", role=User.ROLE_ADMIN, branch=self.branch)
		self.admin = User.objects.create_superuser(username="admin", password="test-password")
		self.product = Product.objects.create(name="Producto", sku="PROD", cost_price=Decimal("3.00"))
		self.supplier = Supplier.objects.create(name="Proveedor")
		self.purchase = Purchase.objects.create(branch=self.branch, supplier=self.supplier, created_by=self.operator)
		self.item = PurchaseItem.objects.create(
			purchase=self.purchase, product=self.product, quantity=5, unit_cost=4, sale_price=6, update_cost=True,
		)
		confirm_purchase(purchase=self.purchase, user=self.operator)
		self.purchase.refresh_from_db()
		self.client.force_login(self.admin)

	def test_purchase_and_lines_are_visible_but_not_editable(self):
		change_url = reverse("admin:purchases_purchase_change", args=[self.purchase.pk])
		response = self.client.get(change_url)
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, self.product.name)
		self.assertNotContains(response, 'name="items-0-quantity"')
		self.assertNotContains(response, "Añadir otro")
		response = self.client.post(change_url, {
			"status": Purchase.STATUS_CANCELLED, "items-TOTAL_FORMS": "1", "items-INITIAL_FORMS": "1",
			"items-0-id": self.item.pk, "items-0-DELETE": "on", "_save": "Save",
		})
		self.assertEqual(response.status_code, 403)
		for method in (self.client.get, self.client.post):
			self.assertEqual(method(reverse("admin:purchases_purchase_add")).status_code, 403)
			self.assertEqual(method(reverse("admin:purchases_purchase_delete", args=[self.purchase.pk])).status_code, 403)
		self.purchase.refresh_from_db()
		self.product.refresh_from_db()
		self.assertEqual(self.purchase.status, Purchase.STATUS_CONFIRMED)
		self.assertTrue(self.purchase.items.filter(pk=self.item.pk).exists())
		self.assertEqual(Stock.objects.get(product=self.product, branch=self.branch).quantity, 5)
		self.assertEqual(self.product.cost_price, Decimal("4.00"))
		self.assertIsNotNone(self.purchase.inventory_movement_id)

	def test_bulk_delete_is_unavailable(self):
		response = self.client.post(reverse("admin:purchases_purchase_changelist"), {
			"action": "delete_selected", "_selected_action": [self.purchase.pk], "post": "yes",
		})
		self.assertEqual(response.status_code, 200)
		self.assertTrue(Purchase.objects.filter(pk=self.purchase.pk).exists())
		self.assertTrue(PurchaseItem.objects.filter(pk=self.item.pk).exists())

	def test_supplier_remains_editable(self):
		response = self.client.post(reverse("admin:purchases_supplier_change", args=[self.supplier.pk]), {
			"name": "Proveedor actualizado", "tax_id": "", "phone": "", "email": "", "address": "",
			"is_active": "on", "_save": "Save",
		})
		self.assertEqual(response.status_code, 302)
		self.supplier.refresh_from_db()
		self.assertEqual(self.supplier.name, "Proveedor actualizado")

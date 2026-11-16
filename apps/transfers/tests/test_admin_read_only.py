from django.test import TestCase
from django.urls import reverse

from apps.branches.models import Branch
from apps.inventory.models import Stock
from apps.products.models import Product
from apps.transfers.models import Transfer, TransferItem
from apps.transfers.services import send_transfer
from apps.users.models import User


class TransferAdminReadOnlyTests(TestCase):
	def setUp(self):
		self.origin = Branch.objects.create(name="Central", code="CENTRAL")
		self.destination = Branch.objects.create(name="Norte", code="NORTE")
		self.operator = User.objects.create_user(username="operador", role=User.ROLE_ADMIN, branch=self.origin)
		self.admin = User.objects.create_superuser(username="admin", password="test-password")
		self.product = Product.objects.create(name="Producto", sku="PROD")
		self.stock = Stock.objects.create(branch=self.origin, product=self.product, quantity=5)
		self.transfer = Transfer.objects.create(origin_branch=self.origin, destination_branch=self.destination, created_by=self.operator)
		self.item = TransferItem.objects.create(transfer=self.transfer, product=self.product, requested_quantity=3)
		send_transfer(self.transfer, self.operator)
		self.transfer.refresh_from_db()
		self.item.refresh_from_db()
		self.client.force_login(self.admin)

	def test_transfer_and_lines_are_visible_but_not_editable(self):
		url = reverse("admin:transfers_transfer_change", args=[self.transfer.pk])
		response = self.client.get(url)
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, self.product.name)
		self.assertNotContains(response, 'name="items-0-requested_quantity"')
		self.assertNotContains(response, "Añadir otro")
		response = self.client.post(url, {
			"status": Transfer.STATUS_RECEIVED, "items-TOTAL_FORMS": "1", "items-INITIAL_FORMS": "1",
			"items-0-id": self.item.pk, "items-0-DELETE": "on", "_save": "Save",
		})
		self.assertEqual(response.status_code, 403)
		for method in (self.client.get, self.client.post):
			self.assertEqual(method(reverse("admin:transfers_transfer_add")).status_code, 403)
			self.assertEqual(method(reverse("admin:transfers_transfer_delete", args=[self.transfer.pk])).status_code, 403)
		self.transfer.refresh_from_db()
		self.item.refresh_from_db()
		self.stock.refresh_from_db()
		self.assertEqual(self.transfer.status, Transfer.STATUS_SENT)
		self.assertEqual(self.item.sent_quantity, 3)
		self.assertEqual(self.stock.quantity, 2)
		self.assertFalse(Stock.objects.filter(branch=self.destination, product=self.product).exists())
		self.assertIsNotNone(self.transfer.outgoing_movement_id)
		self.assertIsNone(self.transfer.incoming_movement_id)

	def test_bulk_delete_is_unavailable(self):
		response = self.client.post(reverse("admin:transfers_transfer_changelist"), {
			"action": "delete_selected", "_selected_action": [self.transfer.pk], "post": "yes",
		})
		self.assertEqual(response.status_code, 200)
		self.assertTrue(Transfer.objects.filter(pk=self.transfer.pk).exists())
		self.assertTrue(TransferItem.objects.filter(pk=self.item.pk).exists())

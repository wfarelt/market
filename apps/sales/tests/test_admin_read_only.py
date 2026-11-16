from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from apps.branches.models import Branch
from apps.cash.models import CashRegister
from apps.cash.services import open_cash_register
from apps.inventory.models import Stock
from apps.products.models import Product
from apps.sales.models import Sale
from apps.sales.services import add_sale_item, confirm_sale, create_sale
from apps.users.models import User


class SaleAdminReadOnlyTests(TestCase):
	def setUp(self):
		self.branch = Branch.objects.create(name="Central", code="CENTRAL")
		self.cashier = User.objects.create_user(username="cajero", role=User.ROLE_CAJERO, branch=self.branch)
		self.admin = User.objects.create_superuser(username="admin", password="test-password")
		self.product = Product.objects.create(name="Producto", sku="PROD", list_price=Decimal("10.00"))
		self.stock = Stock.objects.create(product=self.product, branch=self.branch, quantity=5)
		self.register = open_cash_register(user=self.cashier, opening_amount=Decimal("20.00"))
		self.sale = create_sale(user=self.cashier)
		add_sale_item(sale=self.sale, product=self.product, quantity=2, user=self.cashier)
		confirm_sale(sale=self.sale, user=self.cashier, payment_method=Sale.PAYMENT_CASH, cash_received=Decimal("20.00"))
		self.sale.refresh_from_db()
		self.item = self.sale.items.get()
		self.client.force_login(self.admin)

	def test_sale_and_lines_visible_but_direct_writes_rejected(self):
		change_url = reverse("admin:sales_sale_change", args=[self.sale.pk])
		response = self.client.get(change_url)
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, self.product.name)
		self.assertNotContains(response, 'name="items-0-quantity"')
		self.assertNotContains(response, "Añadir otro")
		response = self.client.post(change_url, {
			"status": Sale.STATUS_CANCELLED,
			"items-TOTAL_FORMS": "1", "items-INITIAL_FORMS": "1",
			"items-0-id": self.item.pk, "items-0-DELETE": "on", "_save": "Save",
		})
		self.assertEqual(response.status_code, 403)
		add_url = reverse("admin:sales_sale_add")
		self.assertEqual(self.client.get(add_url).status_code, 403)
		self.assertEqual(self.client.post(add_url, {"_save": "Save"}).status_code, 403)
		delete_url = reverse("admin:sales_sale_delete", args=[self.sale.pk])
		self.assertEqual(self.client.get(delete_url).status_code, 403)
		self.assertEqual(self.client.post(delete_url, {"post": "yes"}).status_code, 403)
		self.sale.refresh_from_db()
		self.stock.refresh_from_db()
		self.assertEqual(self.sale.status, Sale.STATUS_COMPLETED)
		self.assertEqual(self.sale.total, Decimal("20.00"))
		self.assertEqual(self.stock.quantity, 3)
		self.assertTrue(self.sale.items.filter(pk=self.item.pk).exists())
		self.assertEqual(self.sale.cash_movement.amount, Decimal("20.00"))
		self.assertEqual(CashRegister.objects.get(pk=self.register.pk).total_sales, Decimal("20.00"))

	def test_bulk_delete_is_unavailable(self):
		response = self.client.post(reverse("admin:sales_sale_changelist"), {
			"action": "delete_selected", "_selected_action": [self.sale.pk], "post": "yes",
		})
		self.assertEqual(response.status_code, 200)
		self.assertTrue(Sale.objects.filter(pk=self.sale.pk).exists())
		self.assertTrue(self.sale.items.filter(pk=self.item.pk).exists())

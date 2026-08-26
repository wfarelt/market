from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from apps.branches.models import Branch
from apps.cash.models import CashMovement, CashRegister
from apps.cash.services import open_cash_register
from apps.inventory.models import Stock
from apps.products.models import Product
from apps.sales.models import Sale
from apps.sales.services import add_sale_item, confirm_sale, create_sale
from apps.users.models import User


class SaleServiceTests(TestCase):
	def setUp(self):
		self.branch = Branch.objects.create(name="Central", code="CENTRAL")
		self.user = User.objects.create_user(username="cashier", password="test-password", branch=self.branch, role=User.ROLE_CAJERO)
		open_cash_register(user=self.user, opening_amount=Decimal("100"))
		self.product = Product.objects.create(name="Coca Cola", sku="COCA-600", list_price=Decimal("12.50"))
		Stock.objects.create(product=self.product, branch=self.branch, quantity=Decimal("10"))

	def test_confirm_sale_deducts_stock_and_creates_movements(self):
		sale = create_sale(user=self.user)
		add_sale_item(sale=sale, product=self.product, quantity=2, user=self.user)

		confirm_sale(sale=sale, user=self.user, payment_method=Sale.PAYMENT_CASH, cash_received=Decimal("30"))

		sale.refresh_from_db()
		self.assertEqual(sale.status, Sale.STATUS_COMPLETED)
		self.assertEqual(sale.total, Decimal("25.00"))
		self.assertEqual(sale.change_amount, Decimal("5.00"))
		self.assertEqual(Stock.objects.get(product=self.product, branch=self.branch).quantity, Decimal("8"))
		self.assertEqual(sale.inventory_movement.movement_type, "OUTPUT")
		self.assertEqual(sale.cash_movement.movement_type, CashMovement.TYPE_SALE)

	def test_pos_redirects_to_cash_when_user_has_no_open_register(self):
		self.user.cash_registers.update(status=CashRegister.STATUS_CLOSED)
		self.client.force_login(self.user)

		response = self.client.get(reverse("sales:pos"), follow=True)

		self.assertRedirects(response, reverse("cash:list"))
		self.assertContains(response, "No puedes abrir Ventas sin una caja abierta")


from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from apps.branches.models import Branch
from apps.cash.models import CashMovement, CashRegister
from apps.cash.services import close_cash_register, open_cash_register
from apps.inventory.models import Stock
from apps.products.models import Product
from apps.sales.models import Sale
from apps.sales.services import add_sale_item, confirm_sale, create_sale
from apps.settings_app.models import CompanySettings
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

	def test_confirm_sale_rejects_disabled_payment_method(self):
		settings = CompanySettings.load()
		settings.enable_qr_payment = False
		settings.save(update_fields=["enable_qr_payment", "updated_at"])
		sale = create_sale(user=self.user)
		add_sale_item(sale=sale, product=self.product, quantity=1, user=self.user)

		with self.assertRaisesMessage(ValidationError, "El método de pago seleccionado está deshabilitado."):
			confirm_sale(sale=sale, user=self.user, payment_method=Sale.PAYMENT_QR)

	def test_pos_redirects_to_cash_when_user_has_no_open_register(self):
		self.user.cash_registers.update(status=CashRegister.STATUS_CLOSED)
		self.client.force_login(self.user)

		response = self.client.get(reverse("sales:pos"), follow=True)

		self.assertRedirects(response, reverse("cash:list"))
		self.assertContains(response, "No puedes abrir Ventas sin una caja abierta")

	def test_pos_creates_a_new_draft_for_a_new_cash_register(self):
		old_cash_register = CashRegister.objects.get(user=self.user, status=CashRegister.STATUS_OPEN)
		old_sale = create_sale(user=self.user)
		close_cash_register(cash_register=old_cash_register, user=self.user, closing_amount=Decimal("100"))
		new_cash_register = open_cash_register(user=self.user, opening_amount=Decimal("100"))
		self.client.force_login(self.user)

		response = self.client.get(reverse("sales:pos"))

		self.assertEqual(response.status_code, 200)
		new_sale = Sale.objects.get(user=self.user, status=Sale.STATUS_DRAFT, cash_register=new_cash_register)
		self.assertNotEqual(new_sale.pk, old_sale.pk)

	def test_sale_rejects_fractional_product_quantity(self):
		sale = create_sale(user=self.user)

		with self.assertRaises(ValidationError):
			add_sale_item(sale=sale, product=self.product, quantity=Decimal("1.5"), user=self.user)

	def test_pos_shows_stock_for_the_current_branch(self):
		self.client.force_login(self.user)

		response = self.client.get(reverse("sales:pos"))

		self.assertContains(response, "Disponible: 10")

	def test_pos_renders_keyboard_shortcuts_for_cart_controls(self):
		sale = create_sale(user=self.user)
		add_sale_item(sale=sale, product=self.product, quantity=1, user=self.user)
		self.client.force_login(self.user)

		response = self.client.get(reverse("sales:pos"))

		self.assertContains(response, 'data-cart-row')
		self.assertContains(response, 'data-cart-increase')
		self.assertContains(response, 'data-cart-decrease')
		self.assertContains(response, 'id="pos-cancel"')
		self.assertContains(response, 'event.key === "F2"')
		self.assertContains(response, 'event.key === "F4"')
		self.assertContains(response, 'event.key === "F8"')
		self.assertEqual(response.content.decode().count("const customerSelect ="), 1)
		self.assertContains(response, 'id="checkout-confirmation-modal"')
		self.assertContains(response, 'id="confirm-checkout-button"')
		self.assertContains(response, "confirmation-total")
		self.assertContains(response, "confirmation-change")
		self.assertContains(response, "El monto recibido debe ser igual o mayor al total a cobrar.")
		self.assertContains(response, 'data-icon="cash"')
		self.assertContains(response, 'data-style="success"')
		self.assertContains(response, 'id="confirmation-total"')
		self.assertContains(response, 'id="confirmation-change"')
		self.assertContains(response, 'badge bg-${style}')

	def test_sale_detail_has_shortcuts_to_sales_list_and_pos(self):
		sale = create_sale(user=self.user)
		add_sale_item(sale=sale, product=self.product, quantity=1, user=self.user)
		self.client.force_login(self.user)

		response = self.client.get(reverse("sales:detail", args=[sale.pk]))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, reverse("sales:list"))
		self.assertContains(response, reverse("sales:pos"))
		self.assertContains(response, "Lista de ventas")
		self.assertContains(response, "Punto de venta")

	def test_pos_disables_payment_method_configured_as_unavailable(self):
		settings = CompanySettings.load()
		settings.enable_qr_payment = False
		settings.save(update_fields=["enable_qr_payment", "updated_at"])
		self.client.force_login(self.user)

		response = self.client.get(reverse("sales:pos"))

		self.assertContains(response, 'data-method="QR" data-icon="qr-code" data-style="primary" disabled aria-disabled="true"')

	def test_sale_list_filters_by_date_and_defaults_to_today(self):
		sale = create_sale(user=self.user)
		add_sale_item(sale=sale, product=self.product, quantity=1, user=self.user)
		confirm_sale(sale=sale, user=self.user, payment_method=Sale.PAYMENT_CASH, cash_received=Decimal("20"))
		sale.completed_at = timezone.now() - timedelta(days=1)
		sale.save(update_fields=["completed_at", "updated_at"])
		self.client.force_login(self.user)

		response = self.client.get(reverse("sales:list"))
		self.assertNotContains(response, sale.number)

		response = self.client.get(reverse("sales:list"), {"date": timezone.localdate(sale.completed_at).isoformat()})
		self.assertContains(response, sale.number)


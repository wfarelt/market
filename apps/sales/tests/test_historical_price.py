from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.branches.models import Branch
from apps.cash.models import CashRegister
from apps.cash.services import open_cash_register
from apps.inventory.models import Stock
from apps.products.models import Product
from apps.sales.models import Sale
from apps.sales.services import add_sale_item, confirm_sale, create_sale, update_historical_item_price
from apps.settings_app.models import BusinessDateSettings
from apps.users.models import User


class HistoricalSalePriceTests(TestCase):
	def setUp(self):
		self.branch = Branch.objects.create(name="Central", code="CENTRAL")
		self.user = User.objects.create_user(username="cajero", role=User.ROLE_CAJERO, branch=self.branch)
		self.product = Product.objects.create(name="Producto", sku="PROD", list_price=Decimal("10.00"))
		self.stock = Stock.objects.create(product=self.product, branch=self.branch, quantity=3)
		self.past = timezone.localdate() - timedelta(days=4)
		BusinessDateSettings.objects.filter(pk=1).update(mode=BusinessDateSettings.MODE_HISTORICAL, business_date=self.past)
		self.register = open_cash_register(user=self.user, opening_amount=0)
		self.sale = create_sale(user=self.user)
		add_sale_item(sale=self.sale, product=self.product, quantity=2, user=self.user)
		self.item = self.sale.items.get()
		self.client.force_login(self.user)
		self.url = reverse("sales:update-price", args=[self.item.pk])

	def test_historical_price_saved_per_sale_and_stock_unchanged_until_confirmation(self):
		response = self.client.get(reverse("sales:pos"))
		self.assertContains(response, 'name="unit_price"')
		response = self.client.post(self.url, {"unit_price": "7.25"}, follow=True)
		self.assertContains(response, "Precio de la venta actualizado.")
		self.item.refresh_from_db()
		self.sale.refresh_from_db()
		self.product.refresh_from_db()
		self.stock.refresh_from_db()
		self.assertEqual(self.item.unit_price, Decimal("7.25"))
		self.assertEqual(self.item.subtotal, Decimal("14.50"))
		self.assertEqual(self.sale.total, Decimal("14.50"))
		self.assertEqual(self.product.list_price, Decimal("10.00"))
		self.assertEqual(self.stock.quantity, 3)
		confirm_sale(sale=self.sale, user=self.user, payment_method=Sale.PAYMENT_CASH, cash_received=Decimal("20"))
		self.sale.refresh_from_db()
		self.stock.refresh_from_db()
		self.assertEqual(self.stock.quantity, 1)
		self.assertEqual(self.sale.cash_movement.amount, Decimal("14.50"))
		self.assertEqual(self.sale.inventory_movement.movement_date, self.past)
		with self.assertRaisesMessage(ValidationError, "Solo se pueden modificar ventas en borrador."):
			update_historical_item_price(item=self.item, unit_price="5", user=self.user)

	def test_invalid_prices_report_errors_without_changing_values(self):
		for value in ("", "-1", "1.001", "10000000000.00", "NaN", "texto"):
			with self.subTest(value=value):
				response = self.client.post(self.url, {"unit_price": value}, follow=True)
				self.assertContains(response, 'alert-danger')
				self.item.refresh_from_db()
				self.sale.refresh_from_db()
				self.assertEqual(self.item.unit_price, Decimal("10.00"))
				self.assertEqual(self.sale.total, Decimal("20.00"))

	def test_automatic_mode_rejects_price_changes_even_by_direct_post(self):
		BusinessDateSettings.objects.filter(pk=1).update(mode=BusinessDateSettings.MODE_AUTOMATIC, business_date=None)
		response = self.client.get(reverse("sales:pos"))
		self.assertNotContains(response, 'name="unit_price"')
		response = self.client.post(self.url, {"unit_price": "3.00"}, follow=True)
		self.assertContains(response, "Solo se puede cambiar el precio de una venta durante la carga histórica.")
		self.item.refresh_from_db()
		self.assertEqual(self.item.unit_price, Decimal("10.00"))

	def test_sale_ownership_and_valid_cash_date_are_required(self):
		other = User.objects.create_user(username="otro", role=User.ROLE_CAJERO, branch=self.branch)
		with self.assertRaisesMessage(ValidationError, "No puedes modificar esta venta."):
			update_historical_item_price(item=self.item, unit_price="1", user=other)
		open_cash_register(user=other, opening_amount=0)
		self.client.force_login(other)
		self.assertEqual(self.client.post(self.url, {"unit_price": "1"}).status_code, 404)
		self.client.force_login(self.user)
		CashRegister.objects.filter(pk=self.register.pk).update(business_date=None)
		with self.assertRaisesMessage(ValidationError, "La fecha de negocio de la caja no coincide"):
			update_historical_item_price(item=self.item, unit_price="1", user=self.user)
		CashRegister.objects.filter(pk=self.register.pk).update(business_date=self.past - timedelta(days=1))
		with self.assertRaisesMessage(ValidationError, "La fecha de negocio de la caja no coincide"):
			update_historical_item_price(item=self.item, unit_price="1", user=self.user)
		CashRegister.objects.filter(pk=self.register.pk).update(status=CashRegister.STATUS_CLOSED)
		with self.assertRaisesMessage(ValidationError, "La caja asociada no está abierta."):
			update_historical_item_price(item=self.item, unit_price="1", user=self.user)

	def test_historical_price_does_not_bypass_insufficient_stock(self):
		update_historical_item_price(item=self.item, unit_price="2.00", user=self.user)
		add_sale_item(sale=self.sale, product=self.product, quantity=2, user=self.user)
		with self.assertRaises(ValidationError):
			confirm_sale(sale=self.sale, user=self.user, payment_method=Sale.PAYMENT_QR)
		self.stock.refresh_from_db()
		self.sale.refresh_from_db()
		self.assertEqual(self.stock.quantity, 3)
		self.assertEqual(self.sale.status, Sale.STATUS_DRAFT)
		self.assertIsNone(self.sale.inventory_movement_id)

	def test_discount_and_later_quantity_changes_keep_historical_price(self):
		self.item.discount_amount = Decimal("3.00")
		self.item.save()
		with self.assertRaisesMessage(ValidationError, "El precio no puede ser menor"):
			update_historical_item_price(item=self.item, unit_price="1", user=self.user)
		update_historical_item_price(item=self.item, unit_price="4", user=self.user)
		add_sale_item(sale=self.sale, product=self.product, quantity=1, user=self.user)
		self.item.refresh_from_db()
		self.assertEqual(self.item.unit_price, Decimal("4.00"))
		self.assertEqual(self.item.subtotal, Decimal("9.00"))

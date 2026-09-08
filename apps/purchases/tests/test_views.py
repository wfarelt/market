from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from apps.branches.models import Branch
from apps.products.models import Product
from apps.purchases.models import Purchase, PurchaseItem, Supplier
from apps.users.models import User


class PurchaseViewTests(TestCase):
	def setUp(self):
		self.branch = Branch.objects.create(name="Central", code="CENTRAL")
		self.user = User.objects.create_user(
			username="admin",
			password="test-password",
			branch=self.branch,
			role=User.ROLE_ADMIN,
		)
		self.product = Product.objects.create(
			name="Producto prueba",
			sku="PURCHASE-VIEW-001",
			list_price=Decimal("20.00"),
		)
		self.client.force_login(self.user)

	def test_create_purchase_saves_its_items(self):
		supplier = Supplier.objects.create(name="Proveedor prueba")
		response = self.client.post(
			reverse("purchases:create"),
			{
				"notes": "Compra semanal",
				"supplier": str(supplier.pk),
				"purchase_date": "2026-09-07",
				"invoice_number": "FAC-001",
				"items-TOTAL_FORMS": "1",
				"items-INITIAL_FORMS": "0",
				"items-MIN_NUM_FORMS": "0",
				"items-MAX_NUM_FORMS": "1000",
				"items-0-product": str(self.product.pk),
				"items-0-quantity": "5",
				"items-0-unit_cost": "12.00",
				"items-0-sale_price": "25.00",
			},
		)

		purchase = Purchase.objects.get(notes="Compra semanal")
		self.assertRedirects(response, reverse("purchases:detail", kwargs={"pk": purchase.pk}))
		self.assertEqual(PurchaseItem.objects.filter(purchase=purchase).count(), 1)
		self.assertEqual(purchase.supplier, supplier)
		self.assertEqual(purchase.purchase_date.isoformat(), "2026-09-07")
		self.assertEqual(purchase.invoice_number, "FAC-001")

	def test_admin_can_create_update_and_deactivate_supplier(self):
		response = self.client.post(reverse("purchases:supplier-create"), {"name": "Distribuidora Uno", "phone": "70000000", "is_active": "on"})
		supplier = Supplier.objects.get(name="Distribuidora Uno")
		self.assertRedirects(response, reverse("purchases:supplier-list"))

		response = self.client.post(reverse("purchases:supplier-update", kwargs={"pk": supplier.pk}), {"name": "Distribuidora Dos", "phone": "71111111", "is_active": "on"})
		supplier.refresh_from_db()
		self.assertRedirects(response, reverse("purchases:supplier-list"))
		self.assertEqual(supplier.name, "Distribuidora Dos")

		response = self.client.post(reverse("purchases:supplier-deactivate", kwargs={"pk": supplier.pk}))
		supplier.refresh_from_db()
		self.assertRedirects(response, reverse("purchases:supplier-list"))
		self.assertFalse(supplier.is_active)


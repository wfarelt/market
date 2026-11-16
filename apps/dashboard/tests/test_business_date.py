from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.branches.models import Branch
from apps.cash.models import CashRegister
from apps.inventory.models import Stock
from apps.products.models import Product
from apps.sales.models import Sale
from apps.settings_app.models import BusinessDateSettings
from apps.transfers.models import Transfer
from apps.users.models import User


class DashboardBusinessDateTests(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(name="Central", code="CENTRAL")
        self.other_branch = Branch.objects.create(name="Norte", code="NORTE")
        self.user = User.objects.create_user(username="cajero", role=User.ROLE_CAJERO, branch=self.branch)
        self.other_user = User.objects.create_user(username="otro", role=User.ROLE_CAJERO, branch=self.branch)
        self.foreign_user = User.objects.create_user(username="norte", role=User.ROLE_CAJERO, branch=self.other_branch)
        self.register = CashRegister.objects.create(user=self.user, branch=self.branch, opening_amount=0)
        self.other_register = CashRegister.objects.create(user=self.other_user, branch=self.branch, opening_amount=0)
        self.foreign_register = CashRegister.objects.create(user=self.foreign_user, branch=self.other_branch, opening_amount=0)
        self.today = timezone.localdate()
        self.past = self.today - timedelta(days=4)
        self.client.force_login(self.user)

    def create_sale(self, *, user=None, branch=None, register=None, business_date=None, completed_at=None, status=Sale.STATUS_COMPLETED, total="10.00"):
        return Sale.objects.create(
            user=user or self.user, branch=branch or self.branch, cash_register=register or self.register,
            status=status, total=Decimal(total), business_date=business_date,
            completed_at=completed_at or timezone.now(),
        )

    def enable_historical(self):
        BusinessDateSettings.objects.filter(pk=1).update(
            mode=BusinessDateSettings.MODE_HISTORICAL, business_date=self.past,
        )

    def test_automatic_mode_keeps_registered_date_and_recent_order(self):
        current = self.create_sale(business_date=self.past, total="25.00")
        previous = self.create_sale(business_date=self.today, completed_at=timezone.now() - timedelta(days=4))
        unknown = self.create_sale()
        response = self.client.get(reverse("dashboard:index"))
        self.assertEqual(response.context["today_sales_total"], Decimal("35.00"))
        self.assertEqual(response.context["today_sales_count"], 2)
        self.assertEqual(response.context["unknown_business_dates"], 0)
        self.assertEqual(response.context["selected_date"], self.today)
        self.assertEqual(list(response.context["recent_sales"]), [unknown, current, previous])
        self.assertContains(response, "Ventas de hoy")
        self.assertContains(response, "fecha de venta registrada")
        self.assertNotContains(response, "sin fecha de negocio")

    def test_historical_mode_uses_business_date_and_user_branch_scope(self):
        self.enable_historical()
        included = self.create_sale(business_date=self.past, total="25.00")
        self.create_sale(business_date=self.today, total="200.00")
        self.create_sale(total="100.00")
        self.create_sale(business_date=self.past, status=Sale.STATUS_CANCELLED, total="300.00")
        self.create_sale(user=self.other_user, register=self.other_register, business_date=self.past, total="400.00")
        self.create_sale(user=self.other_user, register=self.other_register)
        self.create_sale(user=self.foreign_user, branch=self.other_branch, register=self.foreign_register, business_date=self.past)
        self.create_sale(user=self.user, branch=self.other_branch, register=self.foreign_register, business_date=self.past)
        self.create_sale(user=self.user, branch=self.other_branch, register=self.foreign_register)
        response = self.client.get(reverse("dashboard:index"))
        self.assertEqual(response.context["today_sales_total"], Decimal("25.00"))
        self.assertEqual(response.context["today_sales_count"], 1)
        self.assertEqual(response.context["unknown_business_dates"], 1)
        self.assertEqual(response.context["selected_date"], self.past)
        self.assertContains(response, "Ventas de la fecha de trabajo")
        self.assertContains(response, self.past.strftime("%d/%m/%Y"))
        self.assertContains(response, "No se incluyen 1 ventas completadas de tu usuario sin fecha de negocio")
        self.assertContains(response, "No se puede determinar si corresponden a la fecha de trabajo")
        self.assertIn(included, response.context["recent_sales"])
        self.assertContains(response, "Todas las fechas, ordenadas por fecha de venta registrada")

    def test_historical_stock_and_pending_transfers_are_current(self):
        self.enable_historical()
        product = Product.objects.create(name="Producto", sku="PROD")
        Stock.objects.create(product=product, branch=self.branch, quantity=0)
        Stock.objects.create(product=product, branch=self.other_branch, quantity=5)
        Transfer.objects.create(origin_branch=self.branch, destination_branch=self.other_branch, status=Transfer.STATUS_SENT)
        response = self.client.get(reverse("dashboard:index"))
        self.assertEqual(response.context["stock_records"], 1)
        self.assertEqual(response.context["out_of_stock"], 1)
        self.assertEqual(response.context["pending_transfers"], 1)
        self.assertContains(response, "Las existencias y los traspasos pendientes muestran el estado actual")

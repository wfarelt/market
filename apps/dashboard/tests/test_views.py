from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.branches.models import Branch
from apps.cash.models import CashRegister
from apps.sales.models import Sale
from apps.users.models import User


class DashboardViewTests(TestCase):
	def test_recent_sales_and_daily_kpi_only_include_current_user_sales(self):
		branch = Branch.objects.create(name="Central", code="CENTRAL")
		user = User.objects.create_user(
			username="cashier",
			password="test-password",
			branch=branch,
			role=User.ROLE_CAJERO,
		)
		other_user = User.objects.create_user(
			username="other-cashier",
			password="test-password",
			branch=branch,
			role=User.ROLE_CAJERO,
		)
		user_register = CashRegister.objects.create(user=user, branch=branch, opening_amount=0)
		other_register = CashRegister.objects.create(user=other_user, branch=branch, opening_amount=0)
		user_sale = Sale.objects.create(user=user, branch=branch, cash_register=user_register, status=Sale.STATUS_COMPLETED, completed_at=timezone.now(), total=Decimal("25.00"))
		other_sale = Sale.objects.create(user=other_user, branch=branch, cash_register=other_register, status=Sale.STATUS_COMPLETED, completed_at=timezone.now(), total=Decimal("100.00"))
		self.client.force_login(user)

		response = self.client.get(reverse("dashboard:index"))

		self.assertEqual(response.status_code, 200)
		self.assertEqual(list(response.context["recent_sales"]), [user_sale])
		self.assertEqual(response.context["today_sales_count"], 1)
		self.assertEqual(response.context["today_sales_total"], Decimal("25.00"))
		self.assertContains(response, user_sale.number)
		self.assertNotContains(response, other_sale.number)

	def test_dashboard_renders_branch_kpis_for_authenticated_user(self):
		branch = Branch.objects.create(name="Central", code="CENTRAL")
		user = User.objects.create_user(
			username="cashier",
			password="test-password",
			branch=branch,
			role=User.ROLE_CAJERO,
		)
		self.client.force_login(user)

		response = self.client.get(reverse("dashboard:index"))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Ventas de hoy")

	def test_cajero_sidebar_hides_restricted_links(self):
		branch = Branch.objects.create(name="Central", code="CENTRAL")
		user = User.objects.create_user(
			username="cashier",
			password="test-password",
			branch=branch,
			role=User.ROLE_CAJERO,
		)
		self.client.force_login(user)

		response = self.client.get(reverse("dashboard:index"))

		self.assertEqual(response.status_code, 200)
		self.assertNotContains(response, reverse("branches:list"))
		self.assertNotContains(response, reverse("products:list"))
		self.assertContains(response, reverse("inventory:list"))
		self.assertNotContains(response, reverse("inventory:movement-list"))
		self.assertNotContains(response, reverse("transfers:list"))
		self.assertContains(response, reverse("cash:list"))
		self.assertContains(response, reverse("sales:pos"))


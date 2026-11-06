from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.branches.models import Branch
from apps.cash.models import CashRegister
from apps.sales.models import Sale
from apps.users.models import User


class SaleListViewTests(TestCase):
	@classmethod
	def setUpTestData(cls):
		cls.branch = Branch.objects.create(name="Central", code="CENTRAL")
		cls.other_branch = Branch.objects.create(name="Norte", code="NORTE")
		cls.admin = User.objects.create_user(username="admin", role=User.ROLE_ADMIN, branch=cls.branch)
		cls.superadmin = User.objects.create_user(username="superadmin", role=User.ROLE_SUPERADMIN)
		cls.cashier = User.objects.create_user(username="cajero", role=User.ROLE_CAJERO, branch=cls.branch)
		cls.other_cashier = User.objects.create_user(username="otro_cajero", role=User.ROLE_CAJERO, branch=cls.branch, is_active=False)
		cls.foreign_cashier = User.objects.create_user(username="cajero_norte", role=User.ROLE_CAJERO, branch=cls.other_branch)
		cls.warehouse_user = User.objects.create_user(username="almacen", role=User.ROLE_ALMACENERO, branch=cls.branch)
		cls.cashier_sale = cls.create_sale(cls.cashier)
		cls.other_sale = cls.create_sale(cls.other_cashier)
		cls.foreign_sale = cls.create_sale(cls.foreign_cashier)

	@classmethod
	def create_sale(cls, user, *, status=Sale.STATUS_COMPLETED, completed_at=None):
		register, _ = CashRegister.objects.get_or_create(
			user=user,
			status=CashRegister.STATUS_OPEN,
			defaults={"branch": user.branch, "opening_amount": Decimal("0.00")},
		)
		return Sale.objects.create(
			user=user,
			branch=user.branch,
			cash_register=register,
			status=status,
			completed_at=completed_at or timezone.now(),
		)

	def test_admin_sees_branch_sales_and_can_filter_any_user(self):
		self.client.force_login(self.admin)
		response = self.client.get(reverse("sales:list"))
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, self.cashier_sale.number)
		self.assertContains(response, self.other_sale.number)
		self.assertNotContains(response, self.foreign_sale.number)
		self.assertContains(response, self.other_cashier.username)
		self.assertContains(response, self.foreign_cashier.username)

		response = self.client.get(reverse("sales:list"), {"user": self.other_cashier.pk})
		self.assertContains(response, self.other_sale.number)
		self.assertNotContains(response, self.cashier_sale.number)
		self.assertContains(response, f'value="{self.other_cashier.pk}" selected')

		response = self.client.get(reverse("sales:list"), {"user": self.foreign_cashier.pk})
		self.assertNotContains(response, self.foreign_sale.number)
		self.assertEqual(list(response.context["sales"]), [])

	def test_superadmin_can_view_all_branches_and_filter_by_user(self):
		self.client.force_login(self.superadmin)
		response = self.client.get(reverse("sales:list"))
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, self.cashier_sale.number)
		self.assertContains(response, self.foreign_sale.number)
		self.assertContains(response, "Ventas registradas en todas las sucursales")

		response = self.client.get(reverse("sales:list"), {"user": self.foreign_cashier.pk})
		self.assertContains(response, self.foreign_sale.number)
		self.assertNotContains(response, self.cashier_sale.number)

	def test_cashier_only_sees_own_sales_even_with_user_parameter(self):
		self.client.force_login(self.cashier)
		response = self.client.get(reverse("sales:list"), {"user": self.other_cashier.pk})
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, self.cashier_sale.number)
		self.assertNotContains(response, self.other_sale.number)
		self.assertNotContains(response, self.foreign_sale.number)
		self.assertNotContains(response, 'name="user"')

	def test_other_roles_keep_existing_access_restriction(self):
		self.client.force_login(self.warehouse_user)
		self.assertEqual(self.client.get(reverse("sales:list")).status_code, 404)

	def test_user_filter_handles_invalid_values_without_error(self):
		self.client.force_login(self.admin)
		for value in ("invalid", "-1", "9999999999999999999999999999", "９"):
			with self.subTest(value=value):
				response = self.client.get(reverse("sales:list"), {"user": value})
				self.assertEqual(response.status_code, 200)
				self.assertEqual(list(response.context["sales"]), [])

	def test_user_filter_combines_with_existing_date_status_and_search(self):
		self.client.force_login(self.admin)
		yesterday = timezone.now() - timedelta(days=1)
		yesterday_sale = self.create_sale(self.cashier, status=Sale.STATUS_CANCELLED, completed_at=yesterday)
		self.create_sale(self.cashier, status=Sale.STATUS_DRAFT)
		response = self.client.get(reverse("sales:list"), {
			"user": self.cashier.pk,
			"date": timezone.localtime(yesterday).date().isoformat(),
			"status": Sale.STATUS_CANCELLED,
			"q": yesterday_sale.number,
		})
		self.assertEqual(list(response.context["sales"]), [yesterday_sale])

	def test_user_filter_is_preserved_in_pagination(self):
		for _ in range(20):
			self.create_sale(self.cashier)
		self.client.force_login(self.admin)
		response = self.client.get(reverse("sales:list"), {"user": self.cashier.pk})
		self.assertTrue(response.context["is_paginated"])
		self.assertContains(response, f'user={self.cashier.pk}&amp;page=2')
		second_page = self.client.get(reverse("sales:list"), {"user": self.cashier.pk, "page": 2})
		self.assertEqual(second_page.context["page_obj"].paginator.count, 21)
		self.assertTrue(all(sale.user_id == self.cashier.pk for sale in second_page.context["sales"]))


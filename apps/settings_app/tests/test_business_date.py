from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.branches.models import Branch
from apps.cash.services import open_cash_register
from apps.settings_app.models import BusinessDateChange, BusinessDateSettings
from apps.settings_app.services import change_business_date, get_business_date
from apps.transfers.models import Transfer
from apps.users.models import User


class BusinessDateTests(TestCase):
	def setUp(self):
		self.branch = Branch.objects.create(name="Central", code="CENTRAL")
		self.other_branch = Branch.objects.create(name="Norte", code="NORTE")
		self.user = User.objects.create_user(username="operador", role=User.ROLE_CAJERO, branch=self.branch)
		self.yesterday = timezone.localdate() - timedelta(days=1)

	def test_automatic_date_uses_local_today(self):
		self.assertEqual(get_business_date(), timezone.localdate())

	@patch("apps.settings_app.services.HISTORICAL_OPERATIONS_SUPPORTED", False)
	def test_historical_mode_is_unavailable_until_integration(self):
		with self.assertRaisesMessage(ValidationError, "El modo histórico todavía no está disponible"):
			change_business_date(user=self.user, mode=BusinessDateSettings.MODE_HISTORICAL, business_date=self.yesterday)
		self.assertEqual(BusinessDateSettings.objects.get(pk=1).mode, BusinessDateSettings.MODE_AUTOMATIC)
		self.assertFalse(BusinessDateChange.objects.exists())

	@patch("apps.settings_app.services.HISTORICAL_OPERATIONS_SUPPORTED", True)
	def test_change_and_return_to_automatic_are_audited(self):
		change_business_date(user=self.user, mode=BusinessDateSettings.MODE_HISTORICAL, business_date=self.yesterday)
		self.assertEqual(get_business_date(), self.yesterday)
		change_business_date(user=self.user, mode=BusinessDateSettings.MODE_AUTOMATIC)
		changes = list(BusinessDateChange.objects.order_by("pk"))
		self.assertEqual(len(changes), 2)
		self.assertEqual((changes[0].previous_mode, changes[0].new_mode, changes[0].new_date),
			(BusinessDateSettings.MODE_AUTOMATIC, BusinessDateSettings.MODE_HISTORICAL, self.yesterday))
		self.assertEqual((changes[1].previous_date, changes[1].new_mode, changes[1].new_date),
			(self.yesterday, BusinessDateSettings.MODE_AUTOMATIC, None))
		self.assertTrue(all(change.created_by == self.user for change in changes))
		self.assertEqual(get_business_date(), timezone.localdate())

	@patch("apps.settings_app.services.HISTORICAL_OPERATIONS_SUPPORTED", True)
	def test_date_can_move_backward_and_forward(self):
		earlier = self.yesterday - timedelta(days=2)
		for value in (self.yesterday, earlier, self.yesterday):
			change_business_date(user=self.user, mode=BusinessDateSettings.MODE_HISTORICAL, business_date=value)
		self.assertEqual(get_business_date(), self.yesterday)
		self.assertEqual(
			list(BusinessDateChange.objects.order_by("pk").values_list("previous_date", "new_date")),
			[(None, self.yesterday), (self.yesterday, earlier), (earlier, self.yesterday)],
		)

	def test_database_enforces_singleton_and_consistent_mode(self):
		with self.assertRaises(IntegrityError), transaction.atomic():
			BusinessDateSettings.objects.create(pk=2)
		with self.assertRaises(IntegrityError), transaction.atomic():
			BusinessDateSettings.objects.filter(pk=1).update(mode=BusinessDateSettings.MODE_HISTORICAL)

	@patch("apps.settings_app.services.HISTORICAL_OPERATIONS_SUPPORTED", True)
	def test_open_register_in_another_branch_blocks_change(self):
		other_user = User.objects.create_user(username="otro", role=User.ROLE_CAJERO, branch=self.other_branch)
		open_cash_register(user=other_user, opening_amount=Decimal("10.00"))
		with self.assertRaisesMessage(ValidationError, "Cierra todas las cajas"):
			change_business_date(user=self.user, mode=BusinessDateSettings.MODE_HISTORICAL, business_date=self.yesterday)
		self.assertFalse(BusinessDateChange.objects.exists())

	@patch("apps.settings_app.services.HISTORICAL_OPERATIONS_SUPPORTED", True)
	def test_sent_transfer_blocks_change(self):
		Transfer.objects.create(origin_branch=self.branch, destination_branch=self.other_branch, status=Transfer.STATUS_SENT)
		with self.assertRaisesMessage(ValidationError, "Recibe los traspasos pendientes"):
			change_business_date(user=self.user, mode=BusinessDateSettings.MODE_HISTORICAL, business_date=self.yesterday)
		self.assertFalse(BusinessDateChange.objects.exists())

	def test_invalid_dates_modes_and_user_are_rejected(self):
		for mode, value in [
			(BusinessDateSettings.MODE_HISTORICAL, None),
			(BusinessDateSettings.MODE_HISTORICAL, timezone.localdate() + timedelta(days=1)),
			(BusinessDateSettings.MODE_AUTOMATIC, self.yesterday),
			("INVALID", None),
		]:
			with self.subTest(mode=mode, value=value), self.assertRaises(ValidationError):
				change_business_date(user=self.user, mode=mode, business_date=value)
		self.user.is_active = False
		with self.assertRaisesMessage(ValidationError, "No tienes permiso"):
			change_business_date(user=self.user, mode=BusinessDateSettings.MODE_AUTOMATIC)
		self.assertFalse(BusinessDateChange.objects.exists())

	@patch("apps.settings_app.services.HISTORICAL_OPERATIONS_SUPPORTED", True)
	def test_same_state_does_not_create_audit_entry(self):
		change_business_date(user=self.user, mode=BusinessDateSettings.MODE_AUTOMATIC)
		self.assertFalse(BusinessDateChange.objects.exists())

	@patch("apps.settings_app.services.HISTORICAL_OPERATIONS_SUPPORTED", False)
	def test_operator_can_see_screen_but_cannot_activate_historical_mode(self):
		self.client.force_login(self.user)
		url = reverse("settings_app:business-date")
		response = self.client.get(url)
		self.assertContains(response, "El modo histórico todavía no está disponible")
		response = self.client.post(url, {
			"mode": BusinessDateSettings.MODE_HISTORICAL,
			"business_date": self.yesterday.isoformat(),
		})
		self.assertContains(response, "El modo histórico todavía no está disponible")
		self.assertFalse(BusinessDateChange.objects.exists())

	@patch("apps.settings_app.services.HISTORICAL_OPERATIONS_SUPPORTED", True)
	def test_unavailable_warning_is_hidden_when_historical_mode_is_supported(self):
		self.client.force_login(self.user)
		url = reverse("settings_app:business-date")
		self.assertNotContains(self.client.get(url), "El modo histórico todavía no está disponible")
		response = self.client.post(url, {
			"mode": BusinessDateSettings.MODE_HISTORICAL,
			"business_date": self.yesterday.isoformat(),
		})
		self.assertRedirects(response, url)
		self.assertEqual(BusinessDateSettings.objects.get(pk=1).business_date, self.yesterday)

	def test_legacy_recovery_is_available_through_settings_screen(self):
		BusinessDateSettings.objects.filter(pk=1).update(
			mode=BusinessDateSettings.MODE_HISTORICAL, business_date=self.yesterday,
		)
		Transfer.objects.create(origin_branch=self.branch, destination_branch=self.other_branch, status=Transfer.STATUS_SENT)
		self.client.force_login(self.user)
		url = reverse("settings_app:business-date")
		self.assertContains(self.client.get(url), "puede volver a automático para recibirlos")
		response = self.client.post(url, {"mode": BusinessDateSettings.MODE_AUTOMATIC, "business_date": ""})
		self.assertRedirects(response, url)
		self.assertEqual(BusinessDateSettings.objects.get(pk=1).mode, BusinessDateSettings.MODE_AUTOMATIC)
		self.assertEqual(BusinessDateChange.objects.count(), 1)

	def test_login_required(self):
		response = self.client.get(reverse("settings_app:business-date"))
		self.assertEqual(response.status_code, 302)
		self.assertIn(reverse("users:login"), response.url)

	@patch("apps.settings_app.services.HISTORICAL_OPERATIONS_SUPPORTED", True)
	def test_historical_indicator_visible_on_other_pages(self):
		change_business_date(user=self.user, mode=BusinessDateSettings.MODE_HISTORICAL, business_date=self.yesterday)
		self.client.force_login(self.user)
		response = self.client.get(reverse("settings_app:business-date"))
		self.assertContains(response, "Carga histórica")
		self.assertContains(response, self.yesterday.strftime("%d/%m/%Y"))

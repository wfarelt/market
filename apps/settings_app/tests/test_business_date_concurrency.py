from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from threading import Event
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection, transaction
from django.test import TransactionTestCase
from django.utils import timezone

from apps.branches.models import Branch
from apps.cash.models import CashMovement, CashRegister
from apps.cash.services import open_cash_register
from apps.inventory.models import InventoryMovement, Stock
from apps.products.models import Product
from apps.settings_app.locking import lock_business_date
from apps.settings_app.models import BusinessDateChange, BusinessDateSettings
from apps.settings_app.services import change_business_date
from apps.transfers.models import Transfer, TransferItem
from apps.transfers.services import send_transfer
from apps.users.models import User


class BusinessDateConcurrencyTests(TransactionTestCase):
	def setUp(self):
		BusinessDateSettings.objects.get_or_create(pk=1)
		self.origin = Branch.objects.create(name="Central", code="CENTRAL")
		self.destination = Branch.objects.create(name="Norte", code="NORTE")
		self.user = User.objects.create_user(username="admin", role=User.ROLE_ADMIN, branch=self.origin)
		self.old_date = timezone.localdate() - timedelta(days=3)
		self.new_date = self.old_date + timedelta(days=1)
		BusinessDateSettings.objects.filter(pk=1).update(
			mode=BusinessDateSettings.MODE_HISTORICAL, business_date=self.old_date,
		)

	def change_date(self):
		return change_business_date(
			user=self.user, mode=BusinessDateSettings.MODE_HISTORICAL, business_date=self.new_date,
		)

	def open_register(self):
		return open_cash_register(user=self.user, opening_amount=Decimal("10.00"))

	def race(self, first, second, second_lock_path):
		ready, attempt, release = Event(), Event(), Event()

		def hold_first():
			close_old_connections()
			try:
				with transaction.atomic():
					first()
					ready.set()
					if not release.wait(10):
						raise AssertionError("La segunda operación no intentó adquirir el bloqueo.")
			finally:
				connection.close()

		def acquire_lock():
			attempt.set()
			return lock_business_date()

		def run_second():
			close_old_connections()
			try:
				try:
					second()
				except ValidationError as error:
					return error
			finally:
				connection.close()
			return None

		with patch("apps.settings_app.services.HISTORICAL_OPERATIONS_SUPPORTED", True):
			with ThreadPoolExecutor(max_workers=2) as executor:
				first_future = executor.submit(hold_first)
				try:
					self.assertTrue(ready.wait(10), "La primera operación no completó su escritura.")
					with patch(second_lock_path, side_effect=acquire_lock):
						second_future = executor.submit(run_second)
						self.assertTrue(attempt.wait(10), "La segunda operación no intentó adquirir el bloqueo.")
						release.set()
						first_future.result(timeout=10)
						return second_future.result(timeout=10)
				finally:
					release.set()

	def assert_busy_or(self, error, expected):
		self.assertIsNotNone(error)
		self.assertTrue(
			"fecha de trabajo está ocupada" in str(error) or expected in str(error),
			str(error),
		)

	def test_open_before_change_keeps_old_date_and_blocks_change(self):
		error = self.race(self.open_register, self.change_date, "apps.settings_app.services.lock_business_date")
		self.assert_busy_or(error, "Cierra todas las cajas")
		self.assertEqual(CashRegister.objects.get().business_date, self.old_date)
		self.assertEqual(CashMovement.objects.count(), 1)
		self.assertEqual(BusinessDateSettings.objects.get(pk=1).business_date, self.old_date)
		self.assertFalse(BusinessDateChange.objects.exists())

	def test_change_before_open_uses_new_date_or_fails_without_partial_register(self):
		error = self.race(self.change_date, self.open_register, "apps.cash.services.lock_business_date")
		if error:
			self.assert_busy_or(error, "fecha de trabajo está ocupada")
			self.assertFalse(CashRegister.objects.exists())
			self.assertFalse(CashMovement.objects.exists())
		else:
			self.assertEqual(CashRegister.objects.get().business_date, self.new_date)
			self.assertEqual(CashMovement.objects.count(), 1)
		self.assertEqual(BusinessDateSettings.objects.get(pk=1).business_date, self.new_date)
		self.assertEqual(BusinessDateChange.objects.count(), 1)

	def create_transfer(self):
		product = Product.objects.create(name="Producto", sku="PRODUCTO")
		stock = Stock.objects.create(branch=self.origin, product=product, quantity=5)
		transfer = Transfer.objects.create(origin_branch=self.origin, destination_branch=self.destination, created_by=self.user)
		TransferItem.objects.create(transfer=transfer, product=product, requested_quantity=3)
		return transfer, stock

	def test_send_before_change_blocks_change(self):
		transfer, stock = self.create_transfer()
		error = self.race(lambda: send_transfer(transfer, self.user), self.change_date, "apps.settings_app.services.lock_business_date")
		self.assert_busy_or(error, "Recibe los traspasos pendientes")
		transfer.refresh_from_db()
		stock.refresh_from_db()
		self.assertEqual((transfer.status, transfer.business_date, stock.quantity), (Transfer.STATUS_SENT, self.old_date, 2))
		self.assertEqual(InventoryMovement.objects.get().movement_date, self.old_date)
		self.assertEqual(BusinessDateSettings.objects.get(pk=1).business_date, self.old_date)
		self.assertFalse(BusinessDateChange.objects.exists())

	def test_change_before_send_uses_new_date_or_fails_without_stock_change(self):
		transfer, stock = self.create_transfer()
		error = self.race(self.change_date, lambda: send_transfer(transfer, self.user), "apps.transfers.services.lock_business_date")
		transfer.refresh_from_db()
		stock.refresh_from_db()
		if error:
			self.assert_busy_or(error, "fecha de trabajo está ocupada")
			self.assertEqual((transfer.status, stock.quantity), (Transfer.STATUS_DRAFT, 5))
			self.assertFalse(InventoryMovement.objects.exists())
		else:
			self.assertEqual((transfer.status, transfer.business_date, stock.quantity), (Transfer.STATUS_SENT, self.new_date, 2))
			self.assertEqual(InventoryMovement.objects.get().movement_date, self.new_date)
		self.assertEqual(BusinessDateSettings.objects.get(pk=1).business_date, self.new_date)
		self.assertEqual(BusinessDateChange.objects.count(), 1)

	def test_sqlite_busy_is_reported_and_leaves_no_partial_register(self):
		if connection.vendor != "sqlite":
			self.skipTest("Esta prueba verifica el comportamiento específico de SQLite.")
		ready, release = Event(), Event()

		def hold_change():
			close_old_connections()
			try:
				with transaction.atomic():
					self.change_date()
					ready.set()
					if not release.wait(10):
						raise AssertionError("La operación competidora no terminó.")
			finally:
				connection.close()

		def try_open():
			close_old_connections()
			try:
				with connection.cursor() as cursor:
					cursor.execute("PRAGMA busy_timeout = 0")
				try:
					self.open_register()
				except ValidationError as error:
					return error
				raise AssertionError("Se abrió una caja mientras SQLite estaba bloqueado.")
			finally:
				connection.close()

		with patch("apps.settings_app.services.HISTORICAL_OPERATIONS_SUPPORTED", True):
			with ThreadPoolExecutor(max_workers=2) as executor:
				first = executor.submit(hold_change)
				try:
					self.assertTrue(ready.wait(10))
					error = executor.submit(try_open).result(timeout=10)
					self.assertIn("fecha de trabajo está ocupada", str(error))
				finally:
					release.set()
				first.result(timeout=10)
		self.assertFalse(CashRegister.objects.exists())
		self.assertFalse(CashMovement.objects.exists())
		self.assertEqual(BusinessDateSettings.objects.get(pk=1).business_date, self.new_date)
		self.assertEqual(BusinessDateChange.objects.count(), 1)

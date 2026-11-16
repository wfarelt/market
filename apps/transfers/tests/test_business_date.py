from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from apps.branches.models import Branch
from apps.inventory.models import InventoryMovement, Stock
from apps.products.models import Product
from apps.cash.services import open_cash_register
from apps.sales.models import Sale
from apps.sales.services import add_sale_item, confirm_sale, create_sale
from apps.settings_app.models import BusinessDateChange, BusinessDateSettings
from apps.settings_app.services import change_business_date
from apps.transfers.models import Transfer, TransferItem
from apps.transfers.services import receive_transfer, send_transfer
from apps.users.models import User


class TransferBusinessDateTests(TestCase):
	def setUp(self):
		self.origin = Branch.objects.create(name="Central", code="CENTRAL")
		self.destination = Branch.objects.create(name="Norte", code="NORTE")
		self.user = User.objects.create_user(username="admin", role=User.ROLE_ADMIN, branch=self.origin)
		self.product = Product.objects.create(name="Producto", sku="PRODUCTO")
		self.stock = Stock.objects.create(branch=self.origin, product=self.product, quantity=5)
		self.historical_date = timezone.localdate() - timedelta(days=4)

	def enable_historical(self, selected_date=None):
		BusinessDateSettings.objects.filter(pk=1).update(
			mode=BusinessDateSettings.MODE_HISTORICAL, business_date=selected_date or self.historical_date,
		)

	def create_transfer(self, quantity=3):
		transfer = Transfer.objects.create(origin_branch=self.origin, destination_branch=self.destination, created_by=self.user)
		TransferItem.objects.create(transfer=transfer, product=self.product, requested_quantity=Decimal(quantity))
		return transfer

	def test_historical_send_and_receive_use_same_date_and_real_times(self):
		self.enable_historical()
		transfer = self.create_transfer()
		before = timezone.now()
		send_transfer(transfer, self.user)
		transfer.refresh_from_db()
		self.stock.refresh_from_db()
		self.assertEqual(transfer.business_date, self.historical_date)
		self.assertEqual(transfer.outgoing_movement.movement_date, self.historical_date)
		self.assertEqual(transfer.outgoing_movement.posted_at, transfer.sent_at)
		self.assertEqual(self.stock.quantity, 2)
		self.assertFalse(Stock.objects.filter(branch=self.destination, product=self.product).exists())
		receive_transfer(transfer, self.user, {})
		after = timezone.now()
		transfer.refresh_from_db()
		self.assertEqual(transfer.incoming_movement.movement_date, self.historical_date)
		self.assertEqual(transfer.incoming_movement.posted_at, transfer.received_at)
		self.assertLessEqual(before, transfer.sent_at)
		self.assertLessEqual(transfer.sent_at, transfer.received_at)
		self.assertLessEqual(transfer.received_at, after)
		self.assertEqual(Stock.objects.get(branch=self.destination, product=self.product).quantity, 3)
		self.client.force_login(self.user)
		for url in (reverse("transfers:detail", args=[transfer.pk]), reverse("transfers:print", args=[transfer.pk])):
			response = self.client.get(url)
			self.assertContains(response, self.historical_date.strftime("%d/%m/%Y"))
			self.assertContains(response, "Fecha de negocio del envío")
			self.assertContains(response, "Envío real")
			self.assertContains(response, "Recepción real")

	def test_insufficient_stock_does_not_create_movement_or_change_transfer(self):
		self.enable_historical()
		transfer = self.create_transfer(quantity=6)
		with self.assertRaisesMessage(ValidationError, "Existencia insuficiente"):
			send_transfer(transfer, self.user)
		transfer.refresh_from_db()
		self.stock.refresh_from_db()
		self.assertEqual(transfer.status, Transfer.STATUS_DRAFT)
		self.assertIsNone(transfer.business_date)
		self.assertIsNone(transfer.sent_at)
		self.assertEqual(self.stock.quantity, 5)
		self.assertFalse(InventoryMovement.objects.exists())

	def test_pending_transfer_blocks_global_date_change(self):
		self.enable_historical()
		transfer = self.create_transfer()
		send_transfer(transfer, self.user)
		with patch("apps.settings_app.services.HISTORICAL_OPERATIONS_SUPPORTED", True):
			with self.assertRaisesMessage(ValidationError, "Recibe los traspasos pendientes"):
				change_business_date(
					user=self.user, mode=BusinessDateSettings.MODE_HISTORICAL,
					business_date=self.historical_date + timedelta(days=1),
				)
		self.assertEqual(BusinessDateSettings.objects.get(pk=1).business_date, self.historical_date)
		self.assertFalse(BusinessDateChange.objects.exists())

	def test_historical_receipt_rejects_mismatch_and_keeps_destination_unchanged(self):
		self.enable_historical()
		transfer = self.create_transfer()
		send_transfer(transfer, self.user)
		self.enable_historical(self.historical_date - timedelta(days=1))
		with self.assertRaisesMessage(ValidationError, "no coincide con la fecha de trabajo"):
			receive_transfer(transfer, self.user, {})
		transfer.refresh_from_db()
		self.assertEqual(transfer.status, Transfer.STATUS_SENT)
		self.assertIsNone(transfer.incoming_movement)
		self.assertFalse(Stock.objects.filter(branch=self.destination).exists())
		self.assertEqual(InventoryMovement.objects.count(), 1)

	def test_legacy_sent_transfer_requires_automatic_mode_for_receipt(self):
		self.enable_historical()
		transfer = Transfer.objects.create(
			origin_branch=self.origin, destination_branch=self.destination, status=Transfer.STATUS_SENT,
		)
		TransferItem.objects.create(transfer=transfer, product=self.product, requested_quantity=3, sent_quantity=3)
		with self.assertRaisesMessage(ValidationError, "El traspaso no tiene fecha de negocio"):
			receive_transfer(transfer, self.user, {})
		transfer.refresh_from_db()
		self.assertEqual(transfer.status, Transfer.STATUS_SENT)
		self.assertFalse(Stock.objects.filter(branch=self.destination).exists())
		self.assertFalse(InventoryMovement.objects.exists())
		BusinessDateSettings.objects.filter(pk=1).update(mode=BusinessDateSettings.MODE_AUTOMATIC, business_date=None)
		receive_transfer(transfer, self.user, {})
		transfer.refresh_from_db()
		self.assertIsNone(transfer.business_date)
		self.assertEqual(Stock.objects.get(branch=self.destination, product=self.product).quantity, 3)

	@patch("apps.settings_app.services.HISTORICAL_OPERATIONS_SUPPORTED", True)
	def test_legacy_pending_transfer_can_be_recovered_via_automatic_mode(self):
		self.enable_historical()
		transfer = Transfer.objects.create(
			origin_branch=self.origin, destination_branch=self.destination, status=Transfer.STATUS_SENT,
		)
		TransferItem.objects.create(transfer=transfer, product=self.product, requested_quantity=3, sent_quantity=3)
		change_business_date(user=self.user, mode=BusinessDateSettings.MODE_AUTOMATIC)
		self.assertFalse(Stock.objects.filter(branch=self.destination).exists())
		self.assertFalse(InventoryMovement.objects.exists())
		change = BusinessDateChange.objects.get()
		self.assertEqual((change.previous_mode, change.previous_date, change.new_mode, change.new_date),
			(BusinessDateSettings.MODE_HISTORICAL, self.historical_date, BusinessDateSettings.MODE_AUTOMATIC, None))
		self.assertEqual(change.created_by, self.user)
		with self.assertRaisesMessage(ValidationError, "Recibe los traspasos pendientes"):
			change_business_date(user=self.user, mode=BusinessDateSettings.MODE_HISTORICAL, business_date=self.historical_date)
		receive_transfer(transfer, self.user, {})
		transfer.refresh_from_db()
		self.assertEqual(transfer.status, Transfer.STATUS_RECEIVED)
		self.assertIsNone(transfer.business_date)
		self.assertEqual(transfer.incoming_movement.movement_date, timezone.localdate())
		self.assertEqual(Stock.objects.get(branch=self.destination, product=self.product).quantity, 3)
		change_business_date(user=self.user, mode=BusinessDateSettings.MODE_HISTORICAL, business_date=self.historical_date)
		self.assertEqual(BusinessDateSettings.objects.get(pk=1).business_date, self.historical_date)
		self.assertEqual(BusinessDateChange.objects.count(), 2)

	@patch("apps.settings_app.services.HISTORICAL_OPERATIONS_SUPPORTED", True)
	def test_legacy_recovery_requires_all_cash_registers_closed(self):
		self.enable_historical()
		Transfer.objects.create(origin_branch=self.origin, destination_branch=self.destination, status=Transfer.STATUS_SENT)
		open_cash_register(user=self.user, opening_amount=Decimal("10.00"))
		with self.assertRaisesMessage(ValidationError, "Cierra todas las cajas"):
			change_business_date(user=self.user, mode=BusinessDateSettings.MODE_AUTOMATIC)
		self.assertEqual(BusinessDateSettings.objects.get(pk=1).business_date, self.historical_date)
		self.assertFalse(BusinessDateChange.objects.exists())

	@patch("apps.settings_app.services.HISTORICAL_OPERATIONS_SUPPORTED", True)
	def test_mixed_pending_transfers_require_dated_receipt_before_recovery(self):
		self.enable_historical()
		dated_transfer = self.create_transfer()
		send_transfer(dated_transfer, self.user)
		legacy_transfer = Transfer.objects.create(
			origin_branch=self.origin, destination_branch=self.destination, status=Transfer.STATUS_SENT,
		)
		with self.assertRaisesMessage(ValidationError, "Recibe los traspasos pendientes"):
			change_business_date(user=self.user, mode=BusinessDateSettings.MODE_AUTOMATIC)
		self.assertFalse(BusinessDateChange.objects.exists())
		receive_transfer(dated_transfer, self.user, {})
		change_business_date(user=self.user, mode=BusinessDateSettings.MODE_AUTOMATIC)
		legacy_transfer.refresh_from_db()
		self.assertEqual(legacy_transfer.status, Transfer.STATUS_SENT)
		self.assertIsNone(legacy_transfer.business_date)

	@patch("apps.settings_app.services.HISTORICAL_OPERATIONS_SUPPORTED", True)
	def test_legacy_recovery_does_not_allow_changing_historical_date(self):
		self.enable_historical()
		Transfer.objects.create(origin_branch=self.origin, destination_branch=self.destination, status=Transfer.STATUS_SENT)
		with self.assertRaisesMessage(ValidationError, "Recibe los traspasos pendientes"):
			change_business_date(
				user=self.user, mode=BusinessDateSettings.MODE_HISTORICAL,
				business_date=self.historical_date + timedelta(days=1),
			)
		self.assertEqual(BusinessDateSettings.objects.get(pk=1).business_date, self.historical_date)
		self.assertFalse(BusinessDateChange.objects.exists())

	@patch("apps.settings_app.services.HISTORICAL_OPERATIONS_SUPPORTED", True)
	def test_legacy_recovery_preserves_permissions(self):
		self.enable_historical()
		transfer = Transfer.objects.create(
			origin_branch=self.origin, destination_branch=self.destination, status=Transfer.STATUS_SENT,
		)
		TransferItem.objects.create(transfer=transfer, product=self.product, requested_quantity=3, sent_quantity=3)
		self.user.is_active = False
		with self.assertRaisesMessage(ValidationError, "No tienes permiso"):
			change_business_date(user=self.user, mode=BusinessDateSettings.MODE_AUTOMATIC)
		self.assertFalse(BusinessDateChange.objects.exists())
		self.user.is_active = True
		change_business_date(user=self.user, mode=BusinessDateSettings.MODE_AUTOMATIC)
		origin_operator = User.objects.create_user(username="origen", role=User.ROLE_ALMACENERO, branch=self.origin)
		with self.assertRaisesMessage(ValidationError, "No tienes permiso"):
			receive_transfer(transfer, origin_operator, {})
		self.assertFalse(Stock.objects.filter(branch=self.destination).exists())
		destination_operator = User.objects.create_user(username="destino", role=User.ROLE_ALMACENERO, branch=self.destination)
		receive_transfer(transfer, destination_operator, {})
		self.assertEqual(Stock.objects.get(branch=self.destination, product=self.product).quantity, 3)

	def test_automatic_mode_allows_receipt_next_day(self):
		transfer = self.create_transfer()
		send_transfer(transfer, self.user)
		transfer.refresh_from_db()
		sent_at = transfer.sent_at
		next_day = sent_at + timedelta(days=1)
		with patch("apps.transfers.services.timezone.now", return_value=next_day):
			receive_transfer(transfer, self.user, {})
		transfer.refresh_from_db()
		self.assertEqual(transfer.business_date, timezone.localdate(sent_at))
		self.assertEqual(transfer.outgoing_movement.movement_date, timezone.localdate(sent_at))
		self.assertEqual(transfer.incoming_movement.movement_date, timezone.localdate(next_day))
		self.assertEqual(transfer.incoming_movement.posted_at, next_day)

	def test_permissions_and_invalid_receipt_are_preserved(self):
		self.enable_historical()
		transfer = self.create_transfer()
		outsider = User.objects.create_user(username="norte", role=User.ROLE_ALMACENERO, branch=self.destination)
		with self.assertRaisesMessage(ValidationError, "No tienes permiso"):
			send_transfer(transfer, outsider)
		send_transfer(transfer, self.user)
		origin_operator = User.objects.create_user(username="origen", role=User.ROLE_ALMACENERO, branch=self.origin)
		with self.assertRaisesMessage(ValidationError, "No tienes permiso"):
			receive_transfer(transfer, origin_operator, {})
		item = transfer.items.get()
		with self.assertRaisesMessage(ValidationError, "Cantidad recibida inválida"):
			receive_transfer(transfer, outsider, {item.pk: "4"})
		self.assertFalse(Stock.objects.filter(branch=self.destination).exists())
		receive_transfer(transfer, outsider, {item.pk: "3"})
		self.assertEqual(Stock.objects.get(branch=self.destination, product=self.product).quantity, 3)

	def test_receipt_makes_stock_available_for_historical_sale(self):
		self.enable_historical()
		cashier = User.objects.create_user(username="cajero", role=User.ROLE_CAJERO, branch=self.destination)
		open_cash_register(user=cashier, opening_amount=Decimal("10.00"))
		sale = create_sale(user=cashier)
		add_sale_item(sale=sale, product=self.product, quantity=1, user=cashier)
		with self.assertRaisesMessage(ValidationError, "Existencia insuficiente"):
			confirm_sale(sale=sale, user=cashier, payment_method=Sale.PAYMENT_QR)
		transfer = self.create_transfer()
		send_transfer(transfer, self.user)
		with self.assertRaisesMessage(ValidationError, "Existencia insuficiente"):
			confirm_sale(sale=sale, user=cashier, payment_method=Sale.PAYMENT_QR)
		receive_transfer(transfer, self.user, {})
		confirm_sale(sale=sale, user=cashier, payment_method=Sale.PAYMENT_QR)
		sale.refresh_from_db()
		self.assertEqual(sale.business_date, self.historical_date)
		self.assertEqual(Stock.objects.get(branch=self.destination, product=self.product).quantity, 2)


class TransferBusinessDateMigrationTests(TransactionTestCase):
	def test_existing_transfer_keeps_original_data_and_unknown_business_date(self):
		executor = MigrationExecutor(connection)
		latest_targets = executor.loader.graph.leaf_nodes()
		old_target = [("transfers", "0002_alter_transfer_options_alter_transferitem_options_and_more")]
		try:
			executor.migrate(old_target)
			old_apps = executor.loader.project_state(old_target).apps
			branch_model = old_apps.get_model("branches", "Branch")
			origin = branch_model.objects.create(name="Origen", code="ORIG")
			destination = branch_model.objects.create(name="Destino", code="DEST")
			sent_at = timezone.now()
			transfer = old_apps.get_model("transfers", "Transfer").objects.create(
				number="TRF-OLD", origin_branch=origin, destination_branch=destination,
				status="SENT", sent_at=sent_at,
			)
			executor = MigrationExecutor(connection)
			executor.migrate(latest_targets)
			new_apps = executor.loader.project_state(latest_targets).apps
			migrated = new_apps.get_model("transfers", "Transfer").objects.get(pk=transfer.pk)
			self.assertIsNone(migrated.business_date)
			self.assertEqual(migrated.sent_at, sent_at)
			self.assertEqual(migrated.status, "SENT")
		finally:
			MigrationExecutor(connection).migrate(latest_targets)

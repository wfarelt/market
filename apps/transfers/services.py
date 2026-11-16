from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.inventory.models import InventoryMovement, InventoryMovementLine, Stock
from apps.settings_app.models import BusinessDateSettings
from apps.settings_app.locking import lock_business_date

from .models import Transfer


def _check_operator(user, branch):
	if user.role == user.ROLE_SUPERADMIN or user.role == user.ROLE_ADMIN:
		return
	if user.role != user.ROLE_ALMACENERO or user.branch_id != branch.id:
		raise ValidationError("No tienes permiso para operar esta sucursal.")


@transaction.atomic
def send_transfer(transfer, user):
	date_settings = lock_business_date()
	transfer = Transfer.objects.select_for_update().select_related("origin_branch").get(pk=transfer.pk)
	if transfer.status != Transfer.STATUS_DRAFT:
		raise ValidationError("Solo los borradores pueden enviarse.")
	_check_operator(user, transfer.origin_branch)
	items = list(transfer.items.select_related("product"))
	if not items:
		raise ValidationError("El traspaso debe incluir productos.")
	sent_at = timezone.now()
	business_date = date_settings.business_date if date_settings.mode == BusinessDateSettings.MODE_HISTORICAL else timezone.localdate(sent_at)
	movement = InventoryMovement.objects.create(movement_type=InventoryMovement.TYPE_TRANSFER, branch=transfer.origin_branch, status=InventoryMovement.STATUS_POSTED, movement_date=business_date, posted_at=sent_at, notes=f"Salida por {transfer.number}", created_by=user)
	for item in items:
		item.full_clean()
		stock = Stock.objects.select_for_update().filter(product=item.product, branch=transfer.origin_branch).first()
		if not stock or stock.quantity < item.requested_quantity:
			raise ValidationError(f"Existencia insuficiente para {item.product.name}.")
		item.sent_quantity = item.requested_quantity
		item.save(update_fields=["sent_quantity", "updated_at"])
		stock.quantity -= item.sent_quantity
		stock.save(update_fields=["quantity", "updated_at"])
		InventoryMovementLine.objects.create(movement=movement, product=item.product, quantity=item.sent_quantity, created_by=user)
	transfer.status, transfer.sent_at, transfer.sent_by, transfer.outgoing_movement = Transfer.STATUS_SENT, sent_at, user, movement
	transfer.business_date = business_date
	transfer.save(update_fields=["status", "sent_at", "sent_by", "outgoing_movement", "business_date", "updated_at"])
	return transfer


@transaction.atomic
def receive_transfer(transfer, user, received_quantities):
	date_settings = lock_business_date()
	transfer = Transfer.objects.select_for_update().select_related("destination_branch").get(pk=transfer.pk)
	if transfer.status != Transfer.STATUS_SENT:
		raise ValidationError("Solo los traspasos enviados pueden recibirse.")
	_check_operator(user, transfer.destination_branch)
	if date_settings.mode == BusinessDateSettings.MODE_HISTORICAL:
		if not transfer.business_date:
			raise ValidationError("El traspaso no tiene fecha de negocio. Cierra las cajas, recibe los traspasos con fecha pendientes y cambia a modo automático para recibirlo.")
		if transfer.business_date != date_settings.business_date:
			raise ValidationError("La fecha de negocio del traspaso no coincide con la fecha de trabajo.")
	received_at = timezone.now()
	movement_date = date_settings.business_date if date_settings.mode == BusinessDateSettings.MODE_HISTORICAL else timezone.localdate(received_at)
	movement = InventoryMovement.objects.create(movement_type=InventoryMovement.TYPE_TRANSFER, branch=transfer.destination_branch, status=InventoryMovement.STATUS_POSTED, movement_date=movement_date, posted_at=received_at, notes=f"Entrada por {transfer.number}", created_by=user)
	for item in transfer.items.select_related("product"):
		quantity = Decimal(str(received_quantities.get(item.pk, item.sent_quantity)))
		if quantity < 0 or quantity > item.sent_quantity:
			raise ValidationError(f"Cantidad recibida inválida para {item.product.name}.")
		item.received_quantity = quantity
		item.save(update_fields=["received_quantity", "updated_at"])
		stock, _ = Stock.objects.select_for_update().get_or_create(product=item.product, branch=transfer.destination_branch, defaults={"quantity": 0, "created_by": user})
		stock.quantity += quantity
		stock.save(update_fields=["quantity", "updated_at"])
		if quantity:
			InventoryMovementLine.objects.create(movement=movement, product=item.product, quantity=quantity, created_by=user)
	transfer.status, transfer.received_at, transfer.received_by, transfer.incoming_movement = Transfer.STATUS_RECEIVED, received_at, user, movement
	transfer.save(update_fields=["status", "received_at", "received_by", "incoming_movement", "updated_at"])
	return transfer


@transaction.atomic
def cancel_transfer(transfer, user):
	transfer = Transfer.objects.select_for_update().get(pk=transfer.pk)
	if transfer.status != Transfer.STATUS_DRAFT:
		raise ValidationError("Solo los borradores pueden cancelarse.")
	_check_operator(user, transfer.origin_branch)
	transfer.status, transfer.cancelled_at, transfer.cancelled_by = Transfer.STATUS_CANCELLED, timezone.now(), user
	transfer.save(update_fields=["status", "cancelled_at", "cancelled_by", "updated_at"])
	return transfer

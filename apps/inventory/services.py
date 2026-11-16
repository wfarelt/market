from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.settings_app.models import BusinessDateSettings
from apps.settings_app.locking import lock_business_date

from .models import InventoryMovement, InventoryMovementLine, Stock


@transaction.atomic
def create_initial_stock(*, product, branch, quantity, user):
	date_settings = lock_business_date()
	if quantity < 0 or quantity != int(quantity):
		raise ValidationError("La existencia inicial debe ser un número entero no negativo.")
	try:
		with transaction.atomic():
			stock = Stock.objects.create(product=product, branch=branch, quantity=0, created_by=user)
	except IntegrityError:
		if Stock.objects.filter(product=product, branch=branch).exists():
			raise ValidationError("Ya existe una existencia para este producto y sucursal.")
		raise
	if quantity:
		movement = InventoryMovement.objects.create(
			movement_type=InventoryMovement.TYPE_ENTRY,
			movement_date=date_settings.business_date if date_settings.mode == BusinessDateSettings.MODE_HISTORICAL else timezone.localdate(),
			branch=branch,
			notes="Existencia inicial",
			created_by=user,
		)
		InventoryMovementLine.objects.create(movement=movement, product=product, quantity=quantity, created_by=user)
		post_inventory_movement(movement)
		stock.refresh_from_db()
	return stock


@transaction.atomic
def post_inventory_movement(movement):
	date_settings = lock_business_date()
	movement = InventoryMovement.objects.select_for_update().get(pk=movement.pk)
	if movement.status == InventoryMovement.STATUS_POSTED:
		raise ValidationError("El movimiento ya fue confirmado.")
	if movement.movement_type == InventoryMovement.TYPE_TRANSFER:
		raise ValidationError("Los traspasos se confirman desde el módulo de traspasos.")
	if date_settings.mode == BusinessDateSettings.MODE_HISTORICAL and movement.movement_date != date_settings.business_date:
		raise ValidationError("La fecha del movimiento debe coincidir con la fecha de trabajo. Corrige el borrador o vuelve a su fecha.")

	lines = list(movement.lines.select_related("product"))
	if not lines:
		raise ValidationError("El movimiento debe incluir al menos un producto.")

	for line in lines:
		line.full_clean()
		stock, _ = Stock.objects.select_for_update().get_or_create(
			product=line.product,
			branch=movement.branch,
			defaults={"quantity": 0, "created_by": movement.created_by},
		)
		quantity_change = _quantity_change(movement, line)
		if quantity_change % 1:
			raise ValidationError("La cantidad del movimiento debe ser un número entero.")
		new_quantity = stock.quantity + quantity_change
		if new_quantity < 0:
			raise ValidationError(
				f"Existencia insuficiente para {line.product.name} en {movement.branch.name}."
			)
		stock.quantity = new_quantity
		stock.save(update_fields=["quantity", "updated_at"])

	movement.status = InventoryMovement.STATUS_POSTED
	movement.posted_at = timezone.now()
	movement.save(update_fields=["status", "posted_at", "updated_at"])
	return movement


def _quantity_change(movement, line):
	if movement.movement_type == InventoryMovement.TYPE_ENTRY:
		return line.quantity
	if movement.movement_type == InventoryMovement.TYPE_OUTPUT:
		return -line.quantity
	if movement.movement_type == InventoryMovement.TYPE_ADJUSTMENT:
		if line.adjustment_direction == InventoryMovementLine.ADJUSTMENT_ENTRY:
			return line.quantity
		return -line.quantity
	raise ValidationError("Tipo de movimiento no soportado.")

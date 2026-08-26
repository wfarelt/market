from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import InventoryMovement, InventoryMovementLine, Stock


@transaction.atomic
def post_inventory_movement(movement):
	movement = InventoryMovement.objects.select_for_update().get(pk=movement.pk)
	if movement.status == InventoryMovement.STATUS_POSTED:
		raise ValidationError("El movimiento ya fue confirmado.")
	if movement.movement_type == InventoryMovement.TYPE_TRANSFER:
		raise ValidationError("Los traspasos se confirman desde el módulo de traspasos.")

	lines = list(movement.lines.select_related("product"))
	if not lines:
		raise ValidationError("El movimiento debe incluir al menos un producto.")

	for line in lines:
		line.full_clean()
		stock, _ = Stock.objects.select_for_update().get_or_create(
			product=line.product,
			branch=movement.branch,
			defaults={"quantity": Decimal("0"), "created_by": movement.created_by},
		)
		quantity_change = _quantity_change(movement, line)
		new_quantity = stock.quantity + quantity_change
		if new_quantity < 0:
			raise ValidationError(
				f"Existencia insuficiente para {line.product.name} en {movement.branch.name}."
			)
		stock.quantity = new_quantity
		stock.save(update_fields=["quantity", "updated_at"])

	movement.status = InventoryMovement.STATUS_POSTED
	movement.save(update_fields=["status", "updated_at"])
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


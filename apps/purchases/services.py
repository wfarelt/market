from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.inventory.models import InventoryMovement, InventoryMovementLine
from apps.inventory.services import post_inventory_movement
from apps.settings_app.models import BusinessDateSettings
from apps.settings_app.locking import lock_business_date

from .models import Purchase


@transaction.atomic
def confirm_purchase(*, purchase, user):
	date_settings = lock_business_date()
	purchase = Purchase.objects.select_for_update().prefetch_related("items__product").get(pk=purchase.pk)
	if purchase.status != Purchase.STATUS_DRAFT:
		raise ValidationError("Solo se pueden confirmar compras en borrador.")
	if purchase.branch_id != user.branch_id and user.role != user.ROLE_SUPERADMIN:
		raise ValidationError("No puedes confirmar compras de otra sucursal.")
	if date_settings.mode == BusinessDateSettings.MODE_HISTORICAL and purchase.purchase_date != date_settings.business_date:
		raise ValidationError("La fecha de compra debe coincidir con la fecha de trabajo. Corrige el borrador o vuelve a su fecha.")
	items = list(purchase.items.select_related("product"))
	if not items:
		raise ValidationError("La compra debe incluir al menos un producto.")

	movement_data = {}
	if date_settings.mode == BusinessDateSettings.MODE_HISTORICAL:
		movement_data["movement_date"] = date_settings.business_date
	movement = InventoryMovement.objects.create(movement_type=InventoryMovement.TYPE_ENTRY, branch=purchase.branch, notes=f"Ingreso por compra {purchase.number}", created_by=user, **movement_data)
	for item in items:
		InventoryMovementLine.objects.create(movement=movement, product=item.product, quantity=item.quantity, created_by=user)
	post_inventory_movement(movement)

	for item in items:
		update_fields = []
		if item.update_cost:
			item.product.cost_price = item.unit_cost
			update_fields.append("cost_price")
		if item.update_sale_price:
			item.product.list_price = item.sale_price
			update_fields.append("list_price")
		if update_fields:
			item.product.save(update_fields=[*update_fields, "updated_at"])

	purchase.status = Purchase.STATUS_CONFIRMED
	purchase.inventory_movement = movement
	purchase.confirmed_at = timezone.now()
	purchase.business_date = date_settings.business_date if date_settings.mode == BusinessDateSettings.MODE_HISTORICAL else timezone.localdate(purchase.confirmed_at)
	purchase.save(update_fields=["status", "inventory_movement", "confirmed_at", "business_date", "updated_at"])
	return purchase


@transaction.atomic
def cancel_purchase(*, purchase, user):
	purchase = Purchase.objects.select_for_update().get(pk=purchase.pk)
	if purchase.status != Purchase.STATUS_DRAFT:
		raise ValidationError("Solo se pueden anular compras en borrador.")
	if purchase.branch_id != user.branch_id and user.role != user.ROLE_SUPERADMIN:
		raise ValidationError("No puedes anular compras de otra sucursal.")
	purchase.status = Purchase.STATUS_CANCELLED
	purchase.save(update_fields=["status", "updated_at"])
	return purchase

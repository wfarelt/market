from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.cash.models import CashMovement, CashRegister
from apps.inventory.models import InventoryMovement, InventoryMovementLine
from apps.inventory.services import post_inventory_movement

from .models import Sale, SaleItem


def calculate_totals(sale):
	subtotal = sum((item.unit_price * item.quantity for item in sale.items.all()), Decimal("0"))
	discount = sum((item.discount_amount for item in sale.items.all()), Decimal("0"))
	sale.subtotal, sale.discount_amount, sale.total = subtotal, discount, subtotal - discount
	sale.save(update_fields=["subtotal", "discount_amount", "total", "updated_at"])
	return sale


@transaction.atomic
def create_sale(*, user):
	cash_register = CashRegister.objects.select_for_update().filter(user=user, branch=user.branch, status=CashRegister.STATUS_OPEN).first()
	if not cash_register:
		raise ValidationError("Debes tener una caja abierta en tu sucursal.")
	return Sale.objects.create(branch=user.branch, user=user, cash_register=cash_register, created_by=user)


@transaction.atomic
def add_sale_item(*, sale, product, quantity, user):
	sale = Sale.objects.select_for_update().get(pk=sale.pk)
	if sale.status != Sale.STATUS_DRAFT:
		raise ValidationError("Solo se pueden modificar ventas en borrador.")
	if sale.user_id != user.id or sale.branch_id != user.branch_id:
		raise ValidationError("No puedes modificar esta venta.")
	if not product.is_active:
		raise ValidationError("El producto está inactivo.")
	item, created = SaleItem.objects.get_or_create(sale=sale, product=product, defaults={"quantity": 0, "unit_price": product.list_price, "created_by": user})
	item.quantity += Decimal(str(quantity))
	item.save()
	return calculate_totals(sale)


@transaction.atomic
def confirm_sale(*, sale, user, payment_method, cash_received=None):
	sale = Sale.objects.select_for_update().prefetch_related("items__product").get(pk=sale.pk)
	if sale.status != Sale.STATUS_DRAFT:
		raise ValidationError("La venta ya fue procesada.")
	if sale.user_id != user.id or sale.branch_id != user.branch_id:
		raise ValidationError("No puedes completar esta venta.")
	cash_register = CashRegister.objects.select_for_update().filter(pk=sale.cash_register_id, user=user, branch=sale.branch, status=CashRegister.STATUS_OPEN).first()
	if not cash_register:
		raise ValidationError("La caja asociada no está abierta.")
	if not sale.items.exists():
		raise ValidationError("La venta debe tener al menos un producto.")
	calculate_totals(sale)
	if payment_method == Sale.PAYMENT_CASH:
		cash_received = Decimal(str(cash_received or 0))
		if cash_received < sale.total:
			raise ValidationError("El efectivo recibido es insuficiente.")
		sale.cash_received, sale.change_amount = cash_received, cash_received - sale.total
	else:
		sale.cash_received, sale.change_amount = None, Decimal("0")
	if payment_method == Sale.PAYMENT_CREDIT:
		raise ValidationError("Las ventas a crédito estarán disponibles al integrar Clientes y Créditos.")
	movement = InventoryMovement.objects.create(movement_type=InventoryMovement.TYPE_OUTPUT, branch=sale.branch, notes=f"Salida por venta {sale.number}", created_by=user)
	for item in sale.items.all():
		InventoryMovementLine.objects.create(movement=movement, product=item.product, quantity=item.quantity, created_by=user)
	post_inventory_movement(movement)
	cash_movement = CashMovement.objects.create(cash_register=cash_register, movement_type=CashMovement.TYPE_SALE, amount=sale.total, description=f"Venta {sale.number} ({payment_method})", created_by=user)
	sale.status, sale.payment_method, sale.inventory_movement, sale.cash_movement, sale.completed_at = Sale.STATUS_COMPLETED, payment_method, movement, cash_movement, timezone.now()
	sale.save(update_fields=["status", "payment_method", "cash_received", "change_amount", "inventory_movement", "cash_movement", "completed_at", "updated_at"])
	return sale


from datetime import date
from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.cash.models import CashMovement, CashRegister
from apps.inventory.models import InventoryMovement, InventoryMovementLine
from apps.inventory.services import post_inventory_movement
from apps.settings_app.models import BusinessDateSettings, CompanySettings
from apps.settings_app.locking import lock_business_date
from apps.users.models import User

from .models import Sale, SaleItem


def _validate_unit_quantity(quantity):
	quantity = Decimal(str(quantity))
	if quantity <= 0 or quantity != quantity.to_integral_value():
		raise ValidationError("Los productos se venden únicamente por unidades enteras.")
	return quantity


def calculate_totals(sale, discount_amount=None):
	subtotal = sum((item.unit_price * item.quantity for item in sale.items.all()), Decimal("0"))
	item_discounts = sum((item.discount_amount for item in sale.items.all()), Decimal("0"))
	if discount_amount is not None:
		discount = Decimal(str(discount_amount))
	else:
		discount = sale.discount_amount or item_discounts
	discount = max(Decimal("0"), min(discount, subtotal))
	sale.subtotal = subtotal
	sale.discount_amount = discount
	sale.total = max(Decimal("0"), subtotal - discount)
	sale.save(update_fields=["subtotal", "discount_amount", "total", "updated_at"])
	return sale


@transaction.atomic
def update_sale_discount(*, sale, discount_amount, user):
	sale = Sale.objects.select_for_update().get(pk=sale.pk)
	if sale.status != Sale.STATUS_DRAFT:
		raise ValidationError("Solo se pueden modificar ventas en borrador.")
	if sale.user_id != user.id or sale.branch_id != user.branch_id:
		raise ValidationError("No puedes modificar esta venta.")
	discount_amount = Decimal(str(discount_amount or 0))
	if discount_amount < 0:
		raise ValidationError("El descuento no puede ser negativo.")
	return calculate_totals(sale, discount_amount=discount_amount)


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
	quantity = _validate_unit_quantity(quantity)
	item, created = SaleItem.objects.get_or_create(sale=sale, product=product, defaults={"quantity": 0, "unit_price": product.list_price, "created_by": user})
	item.quantity += quantity
	item.save()
	return calculate_totals(sale)


@transaction.atomic
def update_historical_item_price(*, item, unit_price, user):
	date_settings = lock_business_date()
	if date_settings.mode != BusinessDateSettings.MODE_HISTORICAL:
		raise ValidationError("Solo se puede cambiar el precio de una venta durante la carga histórica.")
	sale = Sale.objects.select_for_update().get(pk=item.sale_id)
	if sale.status != Sale.STATUS_DRAFT:
		raise ValidationError("Solo se pueden modificar ventas en borrador.")
	if sale.user_id != user.id or sale.branch_id != user.branch_id:
		raise ValidationError("No puedes modificar esta venta.")
	cash_register = CashRegister.objects.select_for_update().filter(
		pk=sale.cash_register_id, user=user, branch=sale.branch, status=CashRegister.STATUS_OPEN,
	).first()
	if not cash_register:
		raise ValidationError("La caja asociada no está abierta.")
	if not cash_register.business_date or cash_register.business_date != date_settings.business_date:
		raise ValidationError("La fecha de negocio de la caja no coincide con la fecha de trabajo.")
	item = SaleItem.objects.select_for_update().get(pk=item.pk, sale=sale)
	price = forms.DecimalField(min_value=0, max_digits=12, decimal_places=2).clean(unit_price)
	if price * item.quantity < item.discount_amount:
		raise ValidationError("El precio no puede ser menor que el descuento de la línea.")
	item.unit_price = price
	item.save(update_fields=["unit_price", "subtotal", "updated_at"])
	return calculate_totals(sale)


@transaction.atomic
def clear_sale_items(*, sale, user):
	sale = Sale.objects.select_for_update().get(pk=sale.pk)
	if sale.status != Sale.STATUS_DRAFT:
		raise ValidationError("Solo se pueden modificar ventas en borrador.")
	if sale.user_id != user.id or sale.branch_id != user.branch_id:
		raise ValidationError("No puedes modificar esta venta.")
	sale.items.all().delete()
	return calculate_totals(sale)


@transaction.atomic
def confirm_sale(*, sale, user, payment_method, cash_received=None, customer=None, discount_amount=None, sale_date: date | None = None):
	date_settings = lock_business_date()
	sale = Sale.objects.select_for_update().prefetch_related("items__product").get(pk=sale.pk)
	if sale.status != Sale.STATUS_DRAFT:
		raise ValidationError("La venta ya fue procesada.")
	if not CompanySettings.load().is_payment_method_enabled(payment_method):
		raise ValidationError("El método de pago seleccionado está deshabilitado.")
	if sale.user_id != user.id or sale.branch_id != user.branch_id:
		raise ValidationError("No puedes completar esta venta.")
	cash_register = CashRegister.objects.select_for_update().filter(pk=sale.cash_register_id, user=user, branch=sale.branch, status=CashRegister.STATUS_OPEN).first()
	if not cash_register:
		raise ValidationError("La caja asociada no está abierta.")
	if date_settings.mode == BusinessDateSettings.MODE_HISTORICAL:
		if not cash_register.business_date:
			raise ValidationError("La caja no tiene fecha de negocio. Ciérrala y abre una nueva caja.")
		if cash_register.business_date != date_settings.business_date:
			raise ValidationError("La fecha de negocio de la caja no coincide con la fecha de trabajo.")
		if sale_date is not None and sale_date != cash_register.business_date:
			raise ValidationError("La fecha de venta debe coincidir con la fecha de negocio de la caja.")
		sale_date = cash_register.business_date
	if not sale.items.exists():
		raise ValidationError("La venta debe tener al menos un producto.")
	if discount_amount is not None:
		discount = Decimal(str(discount_amount or 0))
		if discount < 0:
			raise ValidationError("El descuento no puede ser negativo.")
		calculate_totals(sale, discount_amount=discount)
	else:
		calculate_totals(sale)
	if customer:
		sale.customer = customer
	if payment_method == Sale.PAYMENT_CASH:
		cash_received = Decimal(str(cash_received or 0))
		if cash_received < sale.total:
			raise ValidationError("El efectivo recibido es insuficiente.")
		sale.cash_received, sale.change_amount = cash_received, cash_received - sale.total
	else:
		sale.cash_received, sale.change_amount = None, Decimal("0")
	if payment_method == Sale.PAYMENT_CREDIT:
		if not sale.customer_id:
			raise ValidationError("Debes seleccionar un cliente para realizar una venta a crédito.")
	movement_data = {}
	if date_settings.mode == BusinessDateSettings.MODE_HISTORICAL:
		movement_data["movement_date"] = sale_date
	movement = InventoryMovement.objects.create(movement_type=InventoryMovement.TYPE_OUTPUT, branch=sale.branch, notes=f"Salida por venta {sale.number}", created_by=user, **movement_data)
	for item in sale.items.all():
		InventoryMovementLine.objects.create(movement=movement, product=item.product, quantity=item.quantity, created_by=user)
	post_inventory_movement(movement)
	cash_movement = None
	if payment_method != Sale.PAYMENT_CREDIT:
		cash_movement = CashMovement.objects.create(cash_register=cash_register, movement_type=CashMovement.TYPE_SALE, amount=sale.total, description=f"Venta {sale.number} ({payment_method})", created_by=user)
	confirmed_at = timezone.now()
	completed_at = confirmed_at
	if sale_date is not None:
		completed_at = timezone.localtime(completed_at).replace(
			year=sale_date.year,
			month=sale_date.month,
			day=sale_date.day,
		)
	sale.status, sale.payment_method, sale.inventory_movement, sale.cash_movement, sale.completed_at = Sale.STATUS_COMPLETED, payment_method, movement, cash_movement, completed_at
	sale.business_date = sale_date or timezone.localdate(confirmed_at)
	sale.confirmed_at = confirmed_at
	sale.save(update_fields=["status", "payment_method", "customer", "cash_received", "change_amount", "inventory_movement", "cash_movement", "completed_at", "business_date", "confirmed_at", "updated_at"])
	if payment_method == Sale.PAYMENT_CREDIT:
		from apps.customers.services import create_credit_from_sale
		create_credit_from_sale(sale=sale, user=user)
	return sale


@transaction.atomic
def cancel_sale(*, sale, user):
	date_settings = lock_business_date()
	sale = Sale.objects.select_for_update().get(pk=sale.pk)
	if user.role not in {User.ROLE_ADMIN, User.ROLE_SUPERADMIN}:
		raise ValidationError("Solo un administrador puede anular ventas.")
	if user.role == User.ROLE_ADMIN and sale.branch_id != user.branch_id:
		raise ValidationError("Solo puedes anular ventas de tu sucursal.")
	if sale.status != Sale.STATUS_COMPLETED:
		raise ValidationError("Solo se pueden anular ventas completadas.")

	cash_register = CashRegister.objects.select_for_update().get(pk=sale.cash_register_id)
	if cash_register.status != CashRegister.STATUS_OPEN:
		raise ValidationError("No se puede anular una venta cuya caja ya está cerrada.")
	if date_settings.mode == BusinessDateSettings.MODE_HISTORICAL:
		if not sale.business_date or sale.business_date != date_settings.business_date or cash_register.business_date != date_settings.business_date:
			raise ValidationError("La fecha de negocio de la venta no coincide con la fecha de trabajo.")
		movement_date = sale.business_date
	else:
		movement_date = timezone.localdate()

	items = list(sale.items.select_related("product"))
	if not items:
		raise ValidationError("No se puede anular una venta sin productos.")

	credit = None
	if sale.payment_method == Sale.PAYMENT_CREDIT:
		from apps.customers.models import Credit

		credit = Credit.objects.select_for_update().filter(sale=sale).first()
		if not credit:
			raise ValidationError("No se encontró el crédito asociado a la venta.")
		if credit.payments.exists() or credit.status != Credit.STATUS_PENDING or credit.balance != credit.original_amount:
			raise ValidationError("No se puede anular un crédito que ya tiene pagos registrados.")
	elif not sale.cash_movement_id:
		raise ValidationError("No se encontró el movimiento de caja asociado a la venta.")

	inventory_movement = InventoryMovement.objects.create(
		movement_type=InventoryMovement.TYPE_ENTRY,
		movement_date=movement_date,
		branch=sale.branch,
		notes=f"Devolución por anulación de venta {sale.number}",
		created_by=user,
	)
	for item in items:
		InventoryMovementLine.objects.create(
			movement=inventory_movement,
			product=item.product,
			quantity=item.quantity,
			created_by=user,
		)
	post_inventory_movement(inventory_movement)

	cash_movement = None
	if sale.cash_movement_id:
		cash_movement = CashMovement.objects.create(
			cash_register=cash_register,
			movement_type=CashMovement.TYPE_REFUND,
			amount=sale.total,
			description=f"Devolución por anulación de venta {sale.number}",
			created_by=user,
		)

	if credit:
		credit.status = Credit.STATUS_CANCELLED
		credit.balance = Decimal("0")
		credit.save(update_fields=["status", "balance", "updated_at"])

	sale.status = Sale.STATUS_CANCELLED
	sale.cancelled_inventory_movement = inventory_movement
	sale.cancelled_cash_movement = cash_movement
	sale.cancelled_at = timezone.now()
	sale.save(update_fields=[
		"status",
		"cancelled_inventory_movement",
		"cancelled_cash_movement",
		"cancelled_at",
		"updated_at",
	])
	return sale

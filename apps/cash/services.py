from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import CashMovement, CashRegister, PettyCashExpense


@transaction.atomic
def open_cash_register(*, user, opening_amount, notes=""):
	if not user.branch_id:
		raise ValidationError("El usuario debe tener una sucursal asignada.")
	if CashRegister.objects.select_for_update().filter(user=user, status=CashRegister.STATUS_OPEN).exists():
		raise ValidationError("El usuario ya tiene una caja abierta.")
	try:
		cash_register = CashRegister.objects.create(user=user, branch=user.branch, opening_amount=opening_amount, notes=notes, created_by=user)
	except IntegrityError as error:
		raise ValidationError("El usuario ya tiene una caja abierta.") from error
	CashMovement.objects.create(cash_register=cash_register, movement_type=CashMovement.TYPE_OPENING, amount=opening_amount, description="Fondo de apertura", created_by=user)
	return cash_register


@transaction.atomic
def close_cash_register(*, cash_register, user, closing_amount):
	cash_register = CashRegister.objects.select_for_update().get(pk=cash_register.pk)
	if cash_register.status != CashRegister.STATUS_OPEN:
		raise ValidationError("La caja ya está cerrada.")
	if cash_register.user_id != user.id and not user.is_superuser:
		raise ValidationError("Solo quien abrió la caja puede cerrarla.")
	movements = cash_register.movements.exclude(movement_type=CashMovement.TYPE_CLOSING)
	income_types = [CashMovement.TYPE_OPENING, CashMovement.TYPE_SALE, CashMovement.TYPE_CREDIT_COLLECTION]
	expense_types = [CashMovement.TYPE_PETTY_CASH_EXPENSE, CashMovement.TYPE_SMALL_PURCHASE, CashMovement.TYPE_TRAVEL_EXPENSE, CashMovement.TYPE_REFUND]
	expected_amount = sum((movement.amount for movement in movements if movement.movement_type in income_types), start=0) - sum((movement.amount for movement in movements if movement.movement_type in expense_types), start=0)
	cash_register.status = CashRegister.STATUS_CLOSED
	cash_register.closed_at = timezone.now()
	cash_register.closing_amount = closing_amount
	cash_register.expected_amount = expected_amount
	cash_register.difference = closing_amount - expected_amount
	cash_register.save(update_fields=["status", "closed_at", "closing_amount", "expected_amount", "difference", "updated_at"])
	CashMovement.objects.create(cash_register=cash_register, movement_type=CashMovement.TYPE_CLOSING, amount=closing_amount, description="Conteo de cierre", created_by=user)
	return cash_register


@transaction.atomic
def register_petty_cash_expense(*, cash_register, category, concept, amount, user, movement_type=CashMovement.TYPE_PETTY_CASH_EXPENSE):
	cash_register = CashRegister.objects.select_for_update().get(pk=cash_register.pk)
	if cash_register.status != CashRegister.STATUS_OPEN:
		raise ValidationError("La caja está cerrada.")
	current_expenses = cash_register.total_expenses
	if current_expenses + amount > cash_register.opening_amount:
		remaining = cash_register.remaining_petty_cash
		raise ValidationError(
			f"La suma de gastos ({current_expenses + amount} Bs) no puede superar el saldo inicial de caja chica ({cash_register.opening_amount} Bs). Saldo disponible para gastos: {remaining} Bs."
		)
	movement = CashMovement.objects.create(cash_register=cash_register, movement_type=movement_type, amount=amount, description=concept, created_by=user)
	return PettyCashExpense.objects.create(cash_register=cash_register, category=category, concept=concept, amount=amount, user=user, movement=movement, created_by=user)


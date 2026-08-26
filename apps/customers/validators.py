from decimal import Decimal
from django.core.exceptions import ValidationError
from apps.cash.models import CashRegister


def validate_customer_id_document(id_document, exclude_customer_pk=None):
	from .models import Customer
	qs = Customer.objects.filter(id_document=id_document)
	if exclude_customer_pk:
		qs = qs.exclude(pk=exclude_customer_pk)
	if qs.exists():
		raise ValidationError("Ya existe un cliente registrado con este documento de identidad.")


def validate_credit_payment_amount(credit, amount):
	amount = Decimal(str(amount))
	if amount <= 0:
		raise ValidationError("El monto del pago debe ser mayor a cero.")
	if credit.status in [credit.STATUS_PAID, credit.STATUS_CANCELLED]:
		raise ValidationError("No se pueden registrar pagos en créditos totalmente pagados o cancelados.")
	if amount > credit.balance:
		raise ValidationError(f"El monto del pago ({amount}) supera el saldo pendiente ({credit.balance}).")
	return amount


def validate_user_open_cash_register(user):
	cash_register = CashRegister.objects.filter(
		user=user,
		branch=user.branch,
		status=CashRegister.STATUS_OPEN,
	).first()
	if not cash_register:
		raise ValidationError("Debes tener una caja abierta para procesar este cobro.")
	return cash_register

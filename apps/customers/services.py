from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.cash.models import CashMovement
from .models import Credit, CreditPayment, Customer
from .validators import (
	validate_credit_payment_amount,
	validate_customer_id_document,
	validate_user_open_cash_register,
)


@transaction.atomic
def create_customer(*, first_name, last_name, id_document, tax_id="", phone="", address="", email="", is_active=True, user):
	validate_customer_id_document(id_document)
	customer = Customer.objects.create(
		first_name=first_name.strip(),
		last_name=last_name.strip(),
		id_document=id_document.strip(),
		tax_id=tax_id.strip(),
		phone=phone.strip(),
		address=address.strip(),
		email=email.strip(),
		is_active=is_active,
		created_by=user,
	)
	return customer


@transaction.atomic
def update_customer(*, customer, data):
	if "id_document" in data:
		validate_customer_id_document(data["id_document"], exclude_customer_pk=customer.pk)
	for field in ["first_name", "last_name", "id_document", "tax_id", "phone", "address", "email", "is_active"]:
		if field in data:
			val = data[field]
			if isinstance(val, str):
				val = val.strip()
			setattr(customer, field, val)
	customer.save()
	return customer


@transaction.atomic
def toggle_customer_active(*, customer):
	customer.is_active = not customer.is_active
	customer.save(update_fields=["is_active", "updated_at"])
	return customer


@transaction.atomic
def create_credit_from_sale(*, sale, user):
	if sale.payment_method != "CREDIT":
		raise ValidationError("La venta no está marcada como venta a crédito.")
	if not sale.customer_id:
		raise ValidationError("Se requiere un cliente para generar una venta a crédito.")
	if Credit.objects.filter(sale=sale).exists():
		raise ValidationError("Ya existe un crédito asociado a esta venta.")

	credit = Credit.objects.create(
		customer=sale.customer,
		sale=sale,
		branch=sale.branch,
		user=user,
		original_amount=sale.total,
		balance=sale.total,
		status=Credit.STATUS_PENDING,
		created_by=user,
	)
	return credit


@transaction.atomic
def register_credit_payment(*, credit_pk, amount, user, notes=""):
	cash_register = validate_user_open_cash_register(user)
	credit = Credit.objects.select_for_update().select_related("customer", "branch").get(pk=credit_pk)
	amount = validate_credit_payment_amount(credit, amount)

	cash_movement = CashMovement.objects.create(
		cash_register=cash_register,
		movement_type=CashMovement.TYPE_CREDIT_COLLECTION,
		amount=amount,
		description=f"Cobro crédito {credit.number} - Cliente: {credit.customer.full_name}",
		created_by=user,
	)

	credit_payment = CreditPayment.objects.create(
		credit=credit,
		cash_register=cash_register,
		cash_movement=cash_movement,
		user=user,
		amount=amount,
		notes=notes.strip(),
		created_by=user,
	)

	credit.balance -= amount
	if credit.balance == Decimal("0.00"):
		credit.status = Credit.STATUS_PAID
	else:
		credit.status = Credit.STATUS_PARTIAL

	credit.save(update_fields=["balance", "status", "updated_at"])
	return credit_payment


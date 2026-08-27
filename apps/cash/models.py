from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from apps.branches.models import Branch
from apps.core.models import TimeStampedModel


class CashRegister(TimeStampedModel):
	STATUS_OPEN = "OPEN"
	STATUS_CLOSED = "CLOSED"
	STATUS_CHOICES = [(STATUS_OPEN, "Abierta"), (STATUS_CLOSED, "Cerrada")]

	user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="cash_registers")
	branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="cash_registers")
	status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_OPEN)
	opened_at = models.DateTimeField(auto_now_add=True)
	opening_amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
	closed_at = models.DateTimeField(null=True, blank=True)
	closing_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
	expected_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
	difference = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
	notes = models.TextField(blank=True)

	class Meta:
		ordering = ["-opened_at"]
		constraints = [models.UniqueConstraint(fields=["user"], condition=models.Q(status="OPEN"), name="unique_open_cash_register_per_user")]
		verbose_name = "caja"
		verbose_name_plural = "cajas"

	def __str__(self):
		return f"Caja #{self.pk} - {self.user} ({self.branch.code})"

	@property
	def total_sales(self):
		from django.db.models import Sum
		return self.movements.filter(movement_type=CashMovement.TYPE_SALE).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

	@property
	def total_credit_collections(self):
		from django.db.models import Sum
		return self.movements.filter(movement_type=CashMovement.TYPE_CREDIT_COLLECTION).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

	@property
	def total_expenses(self):
		from django.db.models import Sum
		expense_types = [
			CashMovement.TYPE_PETTY_CASH_EXPENSE,
			CashMovement.TYPE_SMALL_PURCHASE,
			CashMovement.TYPE_TRAVEL_EXPENSE,
			CashMovement.TYPE_REFUND,
		]
		return self.movements.filter(movement_type__in=expense_types).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

	@property
	def remaining_petty_cash(self):
		return max(Decimal("0.00"), self.opening_amount - self.total_expenses)

	@property
	def total_cash_income(self):
		return self.total_sales + self.total_credit_collections

	@property
	def current_balance(self):
		return self.remaining_petty_cash + self.total_cash_income


class CashMovement(TimeStampedModel):
	TYPE_OPENING = "OPENING"
	TYPE_CREDIT_COLLECTION = "CREDIT_COLLECTION"
	TYPE_PETTY_CASH_EXPENSE = "PETTY_CASH_EXPENSE"
	TYPE_SMALL_PURCHASE = "SMALL_PURCHASE"
	TYPE_TRAVEL_EXPENSE = "TRAVEL_EXPENSE"
	TYPE_ADJUSTMENT = "ADJUSTMENT"
	TYPE_SALE = "SALE"
	TYPE_REFUND = "REFUND"
	TYPE_CLOSING = "CLOSING"
	TYPE_CHOICES = [(TYPE_OPENING, "Apertura"), (TYPE_SALE, "Venta"), (TYPE_CREDIT_COLLECTION, "Cobro de crédito"), (TYPE_PETTY_CASH_EXPENSE, "Gasto de caja chica"), (TYPE_SMALL_PURCHASE, "Compra menor"), (TYPE_TRAVEL_EXPENSE, "Viático"), (TYPE_ADJUSTMENT, "Ajuste"), (TYPE_REFUND, "Devolución"), (TYPE_CLOSING, "Cierre")]

	cash_register = models.ForeignKey(CashRegister, on_delete=models.CASCADE, related_name="movements")
	movement_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
	amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
	description = models.TextField(blank=True)

	class Meta:
		ordering = ["-created_at"]
		indexes = [models.Index(fields=["cash_register", "-created_at"])]
		verbose_name = "movimiento de caja"
		verbose_name_plural = "movimientos de caja"


class ExpenseCategory(TimeStampedModel):
	name = models.CharField(max_length=100, unique=True)
	is_active = models.BooleanField(default=True)

	class Meta:
		ordering = ["name"]
		verbose_name = "categoría de gasto"
		verbose_name_plural = "categorías de gasto"

	def __str__(self):
		return self.name


class PettyCashExpense(TimeStampedModel):
	cash_register = models.ForeignKey(CashRegister, on_delete=models.PROTECT, related_name="petty_cash_expenses")
	category = models.ForeignKey(ExpenseCategory, on_delete=models.PROTECT, related_name="expenses")
	concept = models.CharField(max_length=255)
	amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0.01)])
	user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="petty_cash_expenses")
	movement = models.OneToOneField(CashMovement, on_delete=models.PROTECT, related_name="petty_cash_expense")

	class Meta:
		ordering = ["-created_at"]
		verbose_name = "gasto de caja chica"
		verbose_name_plural = "gastos de caja chica"


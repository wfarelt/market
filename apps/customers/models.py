from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from apps.branches.models import Branch
from apps.cash.models import CashMovement, CashRegister
from apps.core.models import TimeStampedModel


class Customer(TimeStampedModel):
	code = models.CharField(max_length=20, unique=True, blank=True)
	first_name = models.CharField(max_length=100, verbose_name="nombres")
	last_name = models.CharField(max_length=100, verbose_name="apellidos")
	id_document = models.CharField(max_length=30, unique=True, verbose_name="documento de identidad")
	tax_id = models.CharField(max_length=30, blank=True, default="", verbose_name="NIT")
	phone = models.CharField(max_length=30, blank=True, default="", verbose_name="teléfono")
	address = models.CharField(max_length=255, blank=True, default="", verbose_name="dirección")
	email = models.EmailField(blank=True, default="", verbose_name="correo electrónico")
	is_active = models.BooleanField(default=True, verbose_name="activo")
	created_by = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.PROTECT,
		related_name="created_customers",
		verbose_name="creado por",
	)

	class Meta:
		ordering = ["last_name", "first_name"]
		verbose_name = "cliente"
		verbose_name_plural = "clientes"

	def __str__(self):
		return f"{self.full_name} ({self.id_document})"

	@property
	def full_name(self):
		return f"{self.first_name} {self.last_name}".strip()

	def save(self, *args, **kwargs):
		new = self._state.adding and not self.code
		super().save(*args, **kwargs)
		if new:
			self.code = f"CLI-{self.pk:06d}"
			super().save(update_fields=["code"])


class Credit(TimeStampedModel):
	STATUS_PENDING = "PENDING"
	STATUS_PARTIAL = "PARTIAL"
	STATUS_PAID = "PAID"
	STATUS_CANCELLED = "CANCELLED"
	STATUS_CHOICES = [
		(STATUS_PENDING, "Pendiente"),
		(STATUS_PARTIAL, "Pago parcial"),
		(STATUS_PAID, "Pagado"),
		(STATUS_CANCELLED, "Cancelado"),
	]

	number = models.CharField(max_length=20, unique=True, blank=True)
	customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="credits", verbose_name="cliente")
	sale = models.OneToOneField("sales.Sale", on_delete=models.PROTECT, related_name="credit", verbose_name="venta")
	branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="credits", verbose_name="sucursal")
	user = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.PROTECT,
		related_name="registered_credits",
		verbose_name="usuario",
	)
	original_amount = models.DecimalField(
		max_digits=12,
		decimal_places=2,
		validators=[MinValueValidator(0.01)],
		verbose_name="monto original",
	)
	balance = models.DecimalField(
		max_digits=12,
		decimal_places=2,
		validators=[MinValueValidator(0)],
		verbose_name="saldo pendiente",
	)
	status = models.CharField(
		max_length=15,
		choices=STATUS_CHOICES,
		default=STATUS_PENDING,
		verbose_name="estado",
	)

	class Meta:
		ordering = ["-created_at"]
		verbose_name = "crédito"
		verbose_name_plural = "créditos"

	def __str__(self):
		return f"Crédito {self.number} - {self.customer.full_name}"

	def save(self, *args, **kwargs):
		new = self._state.adding and not self.number
		super().save(*args, **kwargs)
		if new:
			self.number = f"CRE-{self.pk:06d}"
			super().save(update_fields=["number"])


class CreditPayment(TimeStampedModel):
	credit = models.ForeignKey(Credit, on_delete=models.PROTECT, related_name="payments", verbose_name="crédito")
	cash_register = models.ForeignKey(
		CashRegister,
		on_delete=models.PROTECT,
		related_name="credit_payments",
		verbose_name="caja",
	)
	cash_movement = models.OneToOneField(
		CashMovement,
		on_delete=models.PROTECT,
		related_name="credit_payment",
		verbose_name="movimiento de caja",
	)
	user = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.PROTECT,
		related_name="received_credit_payments",
		verbose_name="usuario",
	)
	amount = models.DecimalField(
		max_digits=12,
		decimal_places=2,
		validators=[MinValueValidator(0.01)],
		verbose_name="monto",
	)
	notes = models.TextField(blank=True, default="", verbose_name="observación")

	class Meta:
		ordering = ["-created_at"]
		verbose_name = "pago de crédito"
		verbose_name_plural = "pagos de créditos"

	def __str__(self):
		return f"Pago {self.amount} a {self.credit.number}"


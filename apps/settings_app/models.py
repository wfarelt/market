from django.db import models

from apps.core.models import TimeStampedModel


class CompanySettings(TimeStampedModel):
	"""Singleton with the company data shown in headers, reports and printed documents."""

	name = models.CharField(max_length=150, verbose_name="razón social")
	trade_name = models.CharField(max_length=150, blank=True, verbose_name="nombre comercial")
	tax_id = models.CharField(max_length=20, blank=True, verbose_name="NIT")
	address = models.TextField(blank=True, verbose_name="dirección")
	phone = models.CharField(max_length=20, blank=True, verbose_name="teléfono")
	email = models.EmailField(blank=True)
	logo = models.ImageField(upload_to="company/", blank=True, verbose_name="logo")
	enable_cash_payment = models.BooleanField(default=True, verbose_name="efectivo")
	enable_qr_payment = models.BooleanField(default=True, verbose_name="QR")
	enable_card_payment = models.BooleanField(default=True, verbose_name="tarjeta")
	enable_transfer_payment = models.BooleanField(default=True, verbose_name="transferencia")
	enable_credit_payment = models.BooleanField(default=True, verbose_name="crédito")

	class Meta:
		verbose_name = "configuración de empresa"
		verbose_name_plural = "configuración de empresa"

	def __str__(self):
		return self.trade_name or self.name

	def save(self, *args, **kwargs):
		self.pk = 1
		super().save(*args, **kwargs)

	def delete(self, *args, **kwargs):
		pass

	def is_payment_method_enabled(self, payment_method):
		return {
			"CASH": self.enable_cash_payment,
			"QR": self.enable_qr_payment,
			"CARD": self.enable_card_payment,
			"TRANSFER": self.enable_transfer_payment,
			"CREDIT": self.enable_credit_payment,
		}.get(payment_method, False)

	def enabled_payment_choices(self, choices):
		return [choice for choice in choices if self.is_payment_method_enabled(choice[0])]

	@classmethod
	def load(cls):
		obj, _ = cls.objects.get_or_create(pk=1, defaults={"name": "Mi Empresa"})
		return obj


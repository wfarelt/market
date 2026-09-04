from django.db import models

from apps.core.models import TimeStampedModel


class CompanySettings(TimeStampedModel):
	"""Singleton with the company data shown in headers, reports and printed documents."""

	name = models.CharField(max_length=150, verbose_name="razón social")
	trade_name = models.CharField(max_length=150, blank=True, verbose_name="nombre comercial")
	tax_id = models.CharField(max_length=20, blank=True, verbose_name="NIT")
	address = models.TextField(blank=True)
	phone = models.CharField(max_length=20, blank=True)
	email = models.EmailField(blank=True)

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

	@classmethod
	def load(cls):
		obj, _ = cls.objects.get_or_create(pk=1, defaults={"name": "Mi Empresa"})
		return obj


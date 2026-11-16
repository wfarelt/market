
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.cash.models import CashRegister
from apps.transfers.models import Transfer
from apps.users.models import User

from .models import BusinessDateChange, BusinessDateSettings
from .locking import lock_business_date


# Enable only after all operational modules use the business date.
HISTORICAL_OPERATIONS_SUPPORTED = False


def get_business_date():
	settings = BusinessDateSettings.objects.get(pk=1)
	if settings.mode == BusinessDateSettings.MODE_HISTORICAL:
		return settings.business_date
	return timezone.localdate()


@transaction.atomic
def change_business_date(*, user, mode, business_date=None):
	if not user.is_authenticated or not user.is_active or user.role not in {
		User.ROLE_SUPERADMIN, User.ROLE_ADMIN, User.ROLE_CAJERO, User.ROLE_ALMACENERO,
	}:
		raise ValidationError("No tienes permiso para cambiar la fecha de trabajo.")
	if mode not in {BusinessDateSettings.MODE_AUTOMATIC, BusinessDateSettings.MODE_HISTORICAL}:
		raise ValidationError("El modo de fecha de trabajo no es válido.")
	if mode == BusinessDateSettings.MODE_HISTORICAL:
		if not business_date:
			raise ValidationError("Selecciona una fecha de trabajo.")
		if business_date > timezone.localdate():
			raise ValidationError("La fecha de trabajo no puede ser futura.")
		if not HISTORICAL_OPERATIONS_SUPPORTED:
			raise ValidationError("El modo histórico todavía no está disponible para operaciones.")
	elif business_date is not None:
		raise ValidationError("El modo automático no admite una fecha fija.")

	settings = lock_business_date()
	if settings.mode == mode and settings.business_date == business_date:
		return settings
	if CashRegister.objects.filter(status=CashRegister.STATUS_OPEN).exists():
		raise ValidationError("Cierra todas las cajas antes de cambiar la fecha de trabajo.")
	pending_transfers = Transfer.objects.filter(status=Transfer.STATUS_SENT)
	if pending_transfers.exists():
		legacy_recovery = (
			settings.mode == BusinessDateSettings.MODE_HISTORICAL
			and mode == BusinessDateSettings.MODE_AUTOMATIC
			and not pending_transfers.filter(business_date__isnull=False).exists()
		)
		if not legacy_recovery:
			raise ValidationError("Recibe los traspasos pendientes antes de cambiar la fecha de trabajo.")
	BusinessDateChange.objects.create(
		previous_mode=settings.mode,
		previous_date=settings.business_date,
		new_mode=mode,
		new_date=business_date,
		created_by=user,
	)
	settings.mode = mode
	settings.business_date = business_date
	settings.save(update_fields=["mode", "business_date", "updated_at"])
	return settings

from django.core.exceptions import ValidationError
from django.db import OperationalError, connection, transaction
from django.db.models import F

from .models import BusinessDateSettings


def lock_business_date():
	if not connection.in_atomic_block:
		raise RuntimeError("La fecha de trabajo solo puede bloquearse dentro de una transacción.")
	try:
		with transaction.atomic():
			if connection.vendor == "sqlite":
				# SQLite ignores select_for_update; acquire its writer lock before reading.
				BusinessDateSettings.objects.filter(pk=1).update(mode=F("mode"))
			return BusinessDateSettings.objects.select_for_update().get(pk=1)
	except OperationalError as error:
		cause = error.__cause__
		code = getattr(cause, "sqlite_errorcode", None)
		message = str(cause)
		# Python 3.10 does not expose SQLite error codes on exceptions.
		is_locked = (
			(code is not None and (code & 255) in (5, 6))
			or (code is None and (
				message in {"database is locked", "database table is locked", "database schema is locked"}
				or message.startswith(("database table is locked:", "database schema is locked:"))
			))
		)
		if connection.vendor == "sqlite" and is_locked:
			raise ValidationError("La fecha de trabajo está ocupada por otra operación. Inténtalo nuevamente.") from error
		raise

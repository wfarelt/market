from decimal import Decimal

from django.db.models import DecimalField, ExpressionWrapper, F, Sum

from apps.cash.models import CashRegister
from apps.customers.models import Credit, CreditPayment
from apps.inventory.models import Stock
from apps.purchases.models import Purchase, PurchaseItem
from apps.sales.models import Sale
from apps.users.models import User

DATE_BASIS_PREVIOUS = "previous"
DATE_BASIS_BUSINESS = "business"
DATE_BASIS_REAL = "real"
DATE_BASIS_CHOICES = [
	(DATE_BASIS_PREVIOUS, "Criterio anterior"),
	(DATE_BASIS_BUSINESS, "Fecha de negocio"),
	(DATE_BASIS_REAL, "Fecha real"),
]


def _with_date_range(queryset, field_name, start_date, end_date, *, date_field=False):
	lookup = field_name if date_field else f"{field_name}__date"
	if start_date:
		queryset = queryset.filter(**{f"{lookup}__gte": start_date})
	if end_date:
		queryset = queryset.filter(**{f"{lookup}__lte": end_date})
	return queryset


def get_report_summary(*, user, branch=None, start_date=None, end_date=None, date_basis=DATE_BASIS_PREVIOUS):
	if date_basis not in {DATE_BASIS_PREVIOUS, DATE_BASIS_BUSINESS, DATE_BASIS_REAL}:
		raise ValueError("Criterio de fecha no válido.")
	if user.role != User.ROLE_SUPERADMIN:
		branch = user.branch

	sales = Sale.objects.filter(status=Sale.STATUS_COMPLETED)
	purchases = Purchase.objects.filter(status=Purchase.STATUS_CONFIRMED)
	credits = Credit.objects.exclude(status=Credit.STATUS_CANCELLED)
	payments = CreditPayment.objects.all()
	cash_registers = CashRegister.objects.filter(status=CashRegister.STATUS_CLOSED)
	stock = Stock.objects.all()

	if branch is not None or user.role != User.ROLE_SUPERADMIN:
		sales = sales.filter(branch=branch)
		purchases = purchases.filter(branch=branch)
		credits = credits.filter(branch=branch)
		payments = payments.filter(credit__branch=branch)
		cash_registers = cash_registers.filter(branch=branch)
		stock = stock.filter(branch=branch)

	fields = {
		DATE_BASIS_PREVIOUS: ("completed_at", "confirmed_at", "closed_at"),
		DATE_BASIS_BUSINESS: ("business_date", "business_date", "business_date"),
		DATE_BASIS_REAL: ("confirmed_at", "confirmed_at", "closed_at"),
	}[date_basis]
	sales_field, purchases_field, cash_field = fields
	unknown_dates = {}
	if date_basis != DATE_BASIS_PREVIOUS:
		unknown_dates = {
			"sales": sales.filter(**{f"{sales_field}__isnull": True}).count(),
			"purchases": purchases.filter(**{f"{purchases_field}__isnull": True}).count(),
			"cash_registers": cash_registers.filter(**{f"{cash_field}__isnull": True}).count(),
		}
		sales = sales.filter(**{f"{sales_field}__isnull": False})
		purchases = purchases.filter(**{f"{purchases_field}__isnull": False})
		cash_registers = cash_registers.filter(**{f"{cash_field}__isnull": False})
	is_business_date = date_basis == DATE_BASIS_BUSINESS
	if is_business_date:
		unknown_dates["credits"] = credits.filter(sale__business_date__isnull=True).count()
		unknown_dates["credit_payments"] = payments.filter(business_date__isnull=True).count()
		credits = credits.filter(sale__business_date__isnull=False)
		payments = payments.filter(business_date__isnull=False)
	sales = _with_date_range(sales, sales_field, start_date, end_date, date_field=is_business_date)
	purchases = _with_date_range(purchases, purchases_field, start_date, end_date, date_field=is_business_date)
	credits = _with_date_range(credits, "sale__business_date" if is_business_date else "created_at", start_date, end_date, date_field=is_business_date)
	payments = _with_date_range(payments, "business_date" if is_business_date else "created_at", start_date, end_date, date_field=is_business_date)
	cash_registers = _with_date_range(cash_registers, cash_field, start_date, end_date, date_field=is_business_date)

	sales_total = sales.aggregate(total=Sum("total"))["total"] or Decimal("0.00")
	purchase_items = PurchaseItem.objects.filter(purchase__in=purchases)
	purchases_total = purchase_items.aggregate(total=Sum(ExpressionWrapper(F("quantity") * F("unit_cost"), output_field=DecimalField(max_digits=24, decimal_places=2))))["total"] or Decimal("0.00")
	credit_issued = credits.aggregate(total=Sum("original_amount"))["total"] or Decimal("0.00")
	credit_collected = payments.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
	credit_balance = Credit.objects.exclude(status=Credit.STATUS_CANCELLED)
	if branch is not None or user.role != User.ROLE_SUPERADMIN:
		credit_balance = credit_balance.filter(branch=branch)
	credit_balance = credit_balance.aggregate(total=Sum("balance"))["total"] or Decimal("0.00")
	stock_value = stock.aggregate(total=Sum(ExpressionWrapper(F("quantity") * F("product__cost_price"), output_field=DecimalField(max_digits=24, decimal_places=2))))["total"] or Decimal("0.00")
	cash_difference = cash_registers.aggregate(total=Sum("difference"))["total"] or Decimal("0.00")

	return {
		"sales_total": sales_total,
		"sales_count": sales.count(),
		"sales_by_payment": sales.values("payment_method").annotate(total=Sum("total")).order_by("payment_method"),
		"purchases_total": purchases_total,
		"purchases_count": purchases.count(),
		"purchased_units": purchase_items.aggregate(total=Sum("quantity"))["total"] or Decimal("0.00"),
		"stock_records": stock.count(),
		"out_of_stock": stock.filter(quantity__lte=0).count(),
		"stock_value": stock_value,
		"credit_issued": credit_issued,
		"credit_collected": credit_collected,
		"credit_balance": credit_balance,
		"closed_cash_registers": cash_registers.count(),
		"cash_difference": cash_difference,
		"unknown_dates": unknown_dates,
		"unknown_dates_total": sum(unknown_dates.values()),
	}

from decimal import Decimal

from django.db.models import DecimalField, ExpressionWrapper, F, Sum

from apps.cash.models import CashMovement, CashRegister
from apps.customers.models import Credit, CreditPayment
from apps.inventory.models import Stock
from apps.purchases.models import Purchase, PurchaseItem
from apps.sales.models import Sale
from apps.users.models import User


def _with_date_range(queryset, field_name, start_date, end_date):
	if start_date:
		queryset = queryset.filter(**{f"{field_name}__date__gte": start_date})
	if end_date:
		queryset = queryset.filter(**{f"{field_name}__date__lte": end_date})
	return queryset


def get_report_summary(*, user, branch=None, start_date=None, end_date=None):
	if user.role != User.ROLE_SUPERADMIN:
		branch = user.branch

	sales = Sale.objects.filter(status=Sale.STATUS_COMPLETED)
	purchases = Purchase.objects.filter(status=Purchase.STATUS_CONFIRMED)
	credits = Credit.objects.exclude(status=Credit.STATUS_CANCELLED)
	payments = CreditPayment.objects.all()
	cash_registers = CashRegister.objects.filter(status=CashRegister.STATUS_CLOSED)
	stock = Stock.objects.all()

	if branch:
		sales = sales.filter(branch=branch)
		purchases = purchases.filter(branch=branch)
		credits = credits.filter(branch=branch)
		payments = payments.filter(credit__branch=branch)
		cash_registers = cash_registers.filter(branch=branch)
		stock = stock.filter(branch=branch)

	sales = _with_date_range(sales, "completed_at", start_date, end_date)
	purchases = _with_date_range(purchases, "confirmed_at", start_date, end_date)
	credits = _with_date_range(credits, "created_at", start_date, end_date)
	payments = _with_date_range(payments, "created_at", start_date, end_date)
	cash_registers = _with_date_range(cash_registers, "closed_at", start_date, end_date)

	sales_total = sales.aggregate(total=Sum("total"))["total"] or Decimal("0.00")
	purchase_items = PurchaseItem.objects.filter(purchase__in=purchases)
	purchases_total = purchase_items.aggregate(total=Sum(ExpressionWrapper(F("quantity") * F("unit_cost"), output_field=DecimalField(max_digits=24, decimal_places=2))))["total"] or Decimal("0.00")
	credit_issued = credits.aggregate(total=Sum("original_amount"))["total"] or Decimal("0.00")
	credit_collected = payments.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
	credit_balance = Credit.objects.exclude(status=Credit.STATUS_CANCELLED)
	if branch:
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
	}

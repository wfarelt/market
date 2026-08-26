from django.db.models import Q, Sum
from apps.users.models import User
from .models import Credit, CreditPayment, Customer


def get_customers_list(user, query=""):
	queryset = Customer.objects.filter(is_active=True)
	if query:
		queryset = queryset.filter(
			Q(first_name__icontains=query)
			| Q(last_name__icontains=query)
			| Q(id_document__icontains=query)
			| Q(phone__icontains=query)
			| Q(code__icontains=query)
		)
	return queryset.order_by("last_name", "first_name")


def get_credits_list(user, filters=None):
	queryset = Credit.objects.select_related("customer", "sale", "branch", "user")
	if user.role != User.ROLE_SUPERADMIN:
		queryset = queryset.filter(branch=user.branch)
	if filters:
		if query := filters.get("q"):
			queryset = queryset.filter(
				Q(number__icontains=query)
				| Q(customer__first_name__icontains=query)
				| Q(customer__last_name__icontains=query)
				| Q(customer__id_document__icontains=query)
			)
		if status := filters.get("status"):
			queryset = queryset.filter(status=status)
		if customer_id := filters.get("customer_id"):
			queryset = queryset.filter(customer_id=customer_id)
	return queryset.order_by("-created_at")


def get_customer_account_statement(customer, user=None):
	credits_qs = Credit.objects.filter(customer=customer).select_related("sale", "branch").prefetch_related("payments")
	if user and user.role != User.ROLE_SUPERADMIN:
		credits_qs = credits_qs.filter(branch=user.branch)
	total_credits = credits_qs.aggregate(total=Sum("original_amount"))["total"] or 0
	total_balance = credits_qs.exclude(status=Credit.STATUS_CANCELLED).aggregate(total=Sum("balance"))["total"] or 0
	total_paid = total_credits - total_balance

	return {
		"customer": customer,
		"credits": credits_qs.order_by("-created_at"),
		"total_credits": total_credits,
		"total_balance": total_balance,
		"total_paid": total_paid,
	}

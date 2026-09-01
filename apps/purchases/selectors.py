from django.db.models import Q

from .models import Purchase


def get_purchases_for_user(user, *, query="", status=""):
	queryset = Purchase.objects.select_related("branch", "created_by").prefetch_related("items")
	if user.role != user.ROLE_SUPERADMIN:
		queryset = queryset.filter(branch=user.branch)
	if query:
		queryset = queryset.filter(Q(number__icontains=query) | Q(notes__icontains=query))
	if status:
		queryset = queryset.filter(status=status)
	return queryset

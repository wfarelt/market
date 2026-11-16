from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum
from django.utils import timezone
from django.views.generic import TemplateView

from apps.cash.models import CashRegister
from apps.inventory.models import Stock
from apps.sales.models import Sale
from apps.settings_app.models import BusinessDateSettings
from apps.transfers.models import Transfer
from apps.users.models import User


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        settings = BusinessDateSettings.objects.get(pk=1)
        historical = settings.mode == BusinessDateSettings.MODE_HISTORICAL
        selected_date = settings.business_date if historical else timezone.localdate()
        sales = Sale.objects.filter(status=Sale.STATUS_COMPLETED)
        stocks = Stock.objects.all()
        transfers = Transfer.objects.all()

        if user.role != User.ROLE_SUPERADMIN:
            sales = sales.filter(branch=user.branch)
            stocks = stocks.filter(branch=user.branch)
            transfers = transfers.filter(origin_branch=user.branch) | transfers.filter(destination_branch=user.branch)

        user_sales = sales.filter(user=user)
        if historical:
            today_sales = user_sales.filter(business_date=selected_date)
            unknown_business_dates = user_sales.filter(business_date__isnull=True).count()
        else:
            today_sales = user_sales.filter(completed_at__date=selected_date)
            unknown_business_dates = 0
        context.update(
            historical_dates=historical,
            selected_date=selected_date,
            unknown_business_dates=unknown_business_dates,
            today_sales_total=today_sales.aggregate(total=Sum("total"))["total"] or 0,
            today_sales_count=today_sales.count(),
            stock_records=stocks.count(),
            out_of_stock=stocks.filter(quantity__lte=0).count(),
            pending_transfers=transfers.filter(status__in=[Transfer.STATUS_DRAFT, Transfer.STATUS_SENT]).count(),
            open_cash_register=CashRegister.objects.filter(user=user, status=CashRegister.STATUS_OPEN).first(),
            recent_sales=user_sales.select_related("user", "branch").order_by("-completed_at")[:5],
            recent_transfers=transfers.select_related("origin_branch", "destination_branch").order_by("-created_at")[:5],
        )
        return context

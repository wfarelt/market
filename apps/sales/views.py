from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import TemplateView

from apps.products.models import Product
from apps.users.models import User
from apps.cash.models import CashRegister

from .forms import CheckoutForm
from .models import Sale, SaleItem
from .services import add_sale_item, confirm_sale, create_sale, calculate_totals


class PosAccessMixin(LoginRequiredMixin):
	def dispatch(self, request, *args, **kwargs):
		if request.user.role not in {User.ROLE_CAJERO, User.ROLE_ADMIN, User.ROLE_SUPERADMIN} or not request.user.branch_id:
			raise Http404
		if not CashRegister.objects.filter(user=request.user, branch=request.user.branch, status=CashRegister.STATUS_OPEN).exists():
			messages.error(request, "No puedes abrir Ventas sin una caja abierta. Abre tu caja antes de continuar.")
			return redirect("cash:list")
		return super().dispatch(request, *args, **kwargs)


class PosView(PosAccessMixin, TemplateView):
	template_name = "sales/pos.html"

	def get_sale(self):
		sale = Sale.objects.filter(user=self.request.user, status=Sale.STATUS_DRAFT).prefetch_related("items__product").first()
		return sale or create_sale(user=self.request.user)

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		sale = self.get_sale()
		query = self.request.GET.get("q", "").strip()
		products = Product.objects.filter(is_active=True)
		if query:
			products = products.filter(Q(sku__icontains=query) | Q(name__icontains=query))[:12]
		else:
			products = products.none()
		context.update(sale=sale, products=products, query=query, checkout_form=CheckoutForm())
		return context


class PosAddItemView(PosAccessMixin, TemplateView):
	def post(self, request, product_id):
		product = get_object_or_404(Product, pk=product_id, is_active=True)
		sale = Sale.objects.filter(user=request.user, status=Sale.STATUS_DRAFT).first() or create_sale(user=request.user)
		try:
			add_sale_item(sale=sale, product=product, quantity=Decimal(str(request.POST.get("quantity", "1"))), user=request.user)
		except ValidationError as error:
			messages.error(request, "; ".join(error.messages))
		return redirect(f"{reverse('sales:pos')}?q={request.POST.get('q', '')}")


class PosUpdateItemView(PosAccessMixin, TemplateView):
	def post(self, request, item_id):
		item = get_object_or_404(SaleItem, pk=item_id, sale__user=request.user, sale__status=Sale.STATUS_DRAFT)
		quantity = Decimal(str(request.POST.get("quantity", "0")))
		if quantity <= 0:
			item.delete()
		else:
			item.quantity = quantity
			item.save()
		calculate_totals(item.sale)
		return redirect("sales:pos")


class PosCheckoutView(PosAccessMixin, TemplateView):
	def post(self, request):
		sale = get_object_or_404(Sale, user=request.user, status=Sale.STATUS_DRAFT)
		form = CheckoutForm(request.POST)
		if form.is_valid():
			try:
				confirm_sale(sale=sale, user=request.user, **form.cleaned_data)
			except ValidationError as error:
				messages.error(request, "; ".join(error.messages))
			else:
				messages.success(request, f"Venta {sale.number} completada correctamente.")
				return redirect("sales:detail", pk=sale.pk)
		else:
			messages.error(request, "Revisa los datos de cobro.")
		return redirect("sales:pos")


class SaleDetailView(PosAccessMixin, TemplateView):
	template_name = "sales/sale_detail.html"
	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context["sale"] = get_object_or_404(Sale.objects.prefetch_related("items__product"), pk=self.kwargs["pk"], user=self.request.user)
		return context


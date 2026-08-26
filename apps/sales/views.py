from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db.models import DecimalField, OuterRef, Q, Subquery, Value
from django.db.models.functions import Coalesce
from django.http import Http404
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import TemplateView

from apps.products.models import Brand, Category, Product
from apps.users.models import User
from apps.cash.models import CashRegister
from apps.inventory.models import Stock

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
	template_name = "sales/pos_quantity.html"

	def get_sale(self):
		sale = Sale.objects.filter(
			user=self.request.user,
			status=Sale.STATUS_DRAFT,
			cash_register__status=CashRegister.STATUS_OPEN,
		).prefetch_related("items__product").first()
		return sale or create_sale(user=self.request.user)

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		sale = self.get_sale()
		query = self.request.GET.get("q", "").strip()
		category_id = self.request.GET.get("category", "")
		brand_id = self.request.GET.get("brand", "")
		products = Product.objects.filter(is_active=True)
		if query:
			products = products.filter(Q(sku__icontains=query) | Q(name__icontains=query))
		if category_id:
			products = products.filter(category_id=category_id)
		if brand_id:
			products = products.filter(brand_id=brand_id)
		available_stock = Stock.objects.filter(
			branch=self.request.user.branch,
			product_id=OuterRef("pk"),
		).values("quantity")[:1]
		products = products.annotate(
			available_stock=Coalesce(
				Subquery(available_stock),
				Value(0),
				output_field=DecimalField(max_digits=15, decimal_places=2),
			)
		)
		context.update(sale=sale, products=products.select_related("category", "brand")[:24], query=query, category_id=category_id, brand_id=brand_id, categories=Category.objects.filter(is_active=True), brands=Brand.objects.filter(is_active=True), checkout_form=CheckoutForm())
		return context


class PosAddItemView(PosAccessMixin, TemplateView):
	def post(self, request, product_id):
		product = get_object_or_404(Product, pk=product_id, is_active=True)
		sale = Sale.objects.filter(
			user=request.user,
			status=Sale.STATUS_DRAFT,
			cash_register__status=CashRegister.STATUS_OPEN,
		).first() or create_sale(user=request.user)
		try:
			add_sale_item(sale=sale, product=product, quantity=Decimal(str(request.POST.get("quantity", "1"))), user=request.user)
		except ValidationError as error:
			messages.error(request, "; ".join(error.messages))
		return redirect(f"{reverse('sales:pos')}?q={request.POST.get('q', '')}")


class PosUpdateItemView(PosAccessMixin, TemplateView):
	def post(self, request, item_id):
		item = get_object_or_404(SaleItem, pk=item_id, sale__user=request.user, sale__status=Sale.STATUS_DRAFT)
		quantity = Decimal(str(request.POST.get("quantity", "0")))
		if quantity != quantity.to_integral_value():
			messages.error(request, "Los productos se venden únicamente por unidades enteras.")
			return redirect("sales:pos")
		if quantity <= 0:
			item.delete()
			removed = True
		else:
			item.quantity = quantity
			item.save()
			removed = False
		sale = calculate_totals(item.sale)
		if request.headers.get("X-Requested-With") == "XMLHttpRequest":
			return JsonResponse({
				"removed": removed,
				"quantity": str(quantity),
				"line_subtotal": str(item.subtotal if not removed else 0),
				"subtotal": str(sale.subtotal),
				"discount": str(sale.discount_amount),
				"total": str(sale.total),
			})
		return redirect("sales:pos")


class PosCheckoutView(PosAccessMixin, TemplateView):
	def post(self, request):
		sale = get_object_or_404(
			Sale,
			user=request.user,
			status=Sale.STATUS_DRAFT,
			cash_register__status=CashRegister.STATUS_OPEN,
		)
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


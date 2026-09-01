from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import CreateView, DetailView, ListView, UpdateView, View

from .forms import PurchaseForm, PurchaseItemFormSet
from .models import Purchase
from .permissions import PurchaseAccessMixin
from .selectors import get_purchases_for_user
from .services import cancel_purchase, confirm_purchase


class PurchaseListView(PurchaseAccessMixin, ListView):
	model = Purchase
	template_name = "purchases/list.html"
	context_object_name = "purchases"
	paginate_by = 20

	def get_queryset(self):
		return get_purchases_for_user(self.request.user, query=self.request.GET.get("q", "").strip(), status=self.request.GET.get("status", ""))

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context["query"] = self.request.GET.get("q", "").strip()
		context["selected_status"] = self.request.GET.get("status", "")
		context["statuses"] = Purchase.STATUS_CHOICES
		return context


class PurchaseFormsetMixin(PurchaseAccessMixin):
	form_class = PurchaseForm
	template_name = "purchases/form.html"

	def get_formset(self):
		return PurchaseItemFormSet(self.request.POST or None, instance=self.object)

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context["formset"] = kwargs.get("formset") or self.get_formset()
		return context

	def form_valid(self, form):
		formset = self.get_formset()
		if not formset.is_valid():
			return self.render_to_response(self.get_context_data(form=form, formset=formset))
		self.object = form.save(commit=False)
		if not self.object.pk:
			self.object.branch = self.request.user.branch
			self.object.created_by = self.request.user
		self.object.save()
		formset.instance = self.object
		instances = formset.save(commit=False)
		for instance in formset.deleted_objects:
			instance.delete()
		for instance in instances:
			if not instance.pk:
				instance.created_by = self.request.user
			instance.save()
		messages.success(self.request, "Compra guardada como borrador.")
		return redirect("purchases:detail", pk=self.object.pk)


class PurchaseCreateView(PurchaseFormsetMixin, CreateView):
	def get(self, request, *args, **kwargs):
		self.object = Purchase()
		return super().get(request, *args, **kwargs)

	def post(self, request, *args, **kwargs):
		self.object = Purchase()
		return super().post(request, *args, **kwargs)


class PurchaseUpdateView(PurchaseFormsetMixin, UpdateView):
	model = Purchase

	def get_queryset(self):
		return get_purchases_for_user(self.request.user, status=Purchase.STATUS_DRAFT)


class PurchaseDetailView(PurchaseAccessMixin, DetailView):
	model = Purchase
	template_name = "purchases/detail.html"
	context_object_name = "purchase"

	def get_queryset(self):
		return get_purchases_for_user(self.request.user).prefetch_related("items__product")


class PurchaseConfirmView(PurchaseAccessMixin, View):
	def post(self, request, pk):
		purchase = get_object_or_404(get_purchases_for_user(request.user), pk=pk)
		try:
			confirm_purchase(purchase=purchase, user=request.user)
		except ValidationError as error:
			messages.error(request, "; ".join(error.messages))
		else:
			messages.success(request, "Compra confirmada e inventario actualizado correctamente.")
		return redirect("purchases:detail", pk=purchase.pk)


class PurchaseCancelView(PurchaseAccessMixin, View):
	def post(self, request, pk):
		purchase = get_object_or_404(get_purchases_for_user(request.user), pk=pk)
		try:
			cancel_purchase(purchase=purchase, user=request.user)
		except ValidationError as error:
			messages.error(request, "; ".join(error.messages))
		else:
			messages.success(request, "Compra anulada correctamente.")
		return redirect("purchases:detail", pk=purchase.pk)


from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from apps.users.models import User

from .forms import InventoryMovementForm, InventoryMovementLineFormSet, StockInitialForm
from .models import InventoryMovement, Stock
from .services import post_inventory_movement


class StockAccessMixin(LoginRequiredMixin, UserPassesTestMixin):
	allowed_roles = {User.ROLE_SUPERADMIN, User.ROLE_ADMIN, User.ROLE_ALMACENERO}

	def test_func(self):
		return self.request.user.role in self.allowed_roles


class StockListView(StockAccessMixin, ListView):
	model = Stock
	template_name = "inventory/list.html"
	context_object_name = "stocks"
	queryset = Stock.objects.select_related("product", "branch", "product__unit_measure")

	def get_queryset(self):
		queryset = super().get_queryset()
		branch_id = self.request.GET.get("branch")
		if branch_id:
			queryset = queryset.filter(branch_id=branch_id)
		return queryset


class StockCreateView(StockAccessMixin, CreateView):
	form_class = StockInitialForm
	template_name = "inventory/form.html"
	success_url = reverse_lazy("inventory:list")
	allowed_roles = {User.ROLE_SUPERADMIN, User.ROLE_ADMIN}

	def form_valid(self, form):
		form.instance.created_by = self.request.user
		messages.success(self.request, "Existencia inicial registrada correctamente.")
		return super().form_valid(form)

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context["title"] = "Registrar existencia inicial"
		return context


class InventoryMovementListView(StockAccessMixin, ListView):
	model = InventoryMovement
	template_name = "inventory/movement_list.html"
	context_object_name = "movements"
	queryset = InventoryMovement.objects.select_related("branch", "created_by")


class InventoryMovementFormsetMixin(StockAccessMixin):
	form_class = InventoryMovementForm
	template_name = "inventory/movement_form.html"

	def get_formset(self, form=None):
		return InventoryMovementLineFormSet(
			self.request.POST or None,
			instance=self.object,
		)

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context["formset"] = kwargs.get("formset") or self.get_formset()
		return context

	def save_formset(self, formset):
		instances = formset.save(commit=False)
		for instance in formset.deleted_objects:
			instance.delete()
		for instance in instances:
			if not instance.pk:
				instance.created_by = self.request.user
			instance.save()


class InventoryMovementCreateView(InventoryMovementFormsetMixin, CreateView):
	def get(self, request, *args, **kwargs):
		self.object = InventoryMovement()
		return super().get(request, *args, **kwargs)

	def post(self, request, *args, **kwargs):
		self.object = InventoryMovement()
		return super().post(request, *args, **kwargs)

	def form_valid(self, form):
		formset = self.get_formset(form)
		if not formset.is_valid():
			return self.render_to_response(self.get_context_data(form=form, formset=formset))
		with transaction.atomic():
			self.object = form.save(commit=False)
			self.object.created_by = self.request.user
			self.object.save()
			formset.instance = self.object
			self.save_formset(formset)
		messages.success(self.request, "Movimiento creado como borrador.")
		return redirect("inventory:movement-detail", pk=self.object.pk)

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context["title"] = "Nuevo movimiento"
		return context


class InventoryMovementUpdateView(InventoryMovementFormsetMixin, UpdateView):
	model = InventoryMovement

	def get_object(self, queryset=None):
		movement = super().get_object(queryset)
		if movement.status != InventoryMovement.STATUS_DRAFT:
			raise Http404
		return movement

	def form_valid(self, form):
		formset = self.get_formset(form)
		if not formset.is_valid():
			return self.render_to_response(self.get_context_data(form=form, formset=formset))
		with transaction.atomic():
			self.object = form.save()
			self.save_formset(formset)
		messages.success(self.request, "Borrador actualizado correctamente.")
		return redirect("inventory:movement-detail", pk=self.object.pk)

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context["title"] = "Editar movimiento"
		return context


class InventoryMovementDetailView(StockAccessMixin, DetailView):
	model = InventoryMovement
	template_name = "inventory/movement_detail.html"
	context_object_name = "movement"

	def get_queryset(self):
		return InventoryMovement.objects.select_related("branch", "created_by").prefetch_related("lines__product")


class InventoryMovementPostView(StockAccessMixin, View):
	def post(self, request, pk):
		movement = get_object_or_404(InventoryMovement, pk=pk)
		try:
			post_inventory_movement(movement)
		except ValidationError as error:
			messages.error(request, "; ".join(error.messages))
		else:
			messages.success(request, "Movimiento confirmado correctamente.")
		return redirect(reverse("inventory:movement-detail", kwargs={"pk": pk}))


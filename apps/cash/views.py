from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import DetailView, FormView, ListView

from apps.users.models import User

from .forms import CashRegisterCloseForm, CashRegisterOpenForm, PettyCashExpenseForm
from .models import CashRegister
from .services import close_cash_register, open_cash_register, register_petty_cash_expense


class CashAccessMixin(LoginRequiredMixin):
	def dispatch(self, request, *args, **kwargs):
		if request.user.role not in {User.ROLE_ADMIN, User.ROLE_CAJERO, User.ROLE_ALMACENERO}:
			raise Http404
		return super().dispatch(request, *args, **kwargs)


class CashRegisterListView(CashAccessMixin, ListView):
	model = CashRegister
	template_name = "cash/list.html"
	context_object_name = "cash_registers"
	paginate_by = 20

	def get_queryset(self):
		queryset = CashRegister.objects.select_related("user", "branch")
		if self.request.user.role == User.ROLE_ADMIN:
			return queryset.filter(branch=self.request.user.branch)
		return queryset.filter(user=self.request.user)

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context["open_register"] = CashRegister.objects.filter(user=self.request.user, status=CashRegister.STATUS_OPEN).first()
		return context


class CashRegisterOpenView(CashAccessMixin, FormView):
	form_class = CashRegisterOpenForm
	template_name = "cash/form.html"
	success_url = reverse_lazy("cash:list")

	def get_last_closed_register(self):
		return CashRegister.objects.filter(user=self.request.user, status=CashRegister.STATUS_CLOSED).order_by("-closed_at").first()

	def get_initial(self):
		initial = super().get_initial()
		last_register = self.get_last_closed_register()
		if last_register:
			initial["opening_amount"] = last_register.remaining_petty_cash
		return initial

	def form_valid(self, form):
		try:
			open_cash_register(user=self.request.user, **form.cleaned_data)
		except ValidationError as error:
			form.add_error(None, error)
			return self.form_invalid(form)
		messages.success(self.request, "Caja abierta correctamente.")
		return super().form_valid(form)

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context["title"] = "Abrir caja"
		last_register = self.get_last_closed_register()
		if last_register:
			context["last_closed_register"] = last_register
			context["suggested_opening_amount"] = last_register.remaining_petty_cash
		return context


class CashRegisterCloseView(CashAccessMixin, FormView):
	form_class = CashRegisterCloseForm
	template_name = "cash/form.html"
	success_url = reverse_lazy("cash:list")

	def dispatch(self, request, *args, **kwargs):
		self.cash_register = get_object_or_404(CashRegister, pk=kwargs["pk"], status=CashRegister.STATUS_OPEN, user=request.user)
		return super().dispatch(request, *args, **kwargs)

	def form_valid(self, form):
		try:
			close_cash_register(cash_register=self.cash_register, user=self.request.user, **form.cleaned_data)
		except ValidationError as error:
			form.add_error(None, error)
			return self.form_invalid(form)
		messages.success(self.request, "Caja cerrada correctamente.")
		return super().form_valid(form)

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context["title"] = f"Cerrar caja #{self.cash_register.pk}"
		context["cash_register"] = self.cash_register
		return context


class PettyCashExpenseCreateView(CashAccessMixin, FormView):
	form_class = PettyCashExpenseForm
	template_name = "cash/form.html"
	success_url = reverse_lazy("cash:list")

	def dispatch(self, request, *args, **kwargs):
		self.cash_register = get_object_or_404(CashRegister, pk=kwargs["pk"], status=CashRegister.STATUS_OPEN, user=request.user)
		return super().dispatch(request, *args, **kwargs)

	def form_valid(self, form):
		try:
			register_petty_cash_expense(cash_register=self.cash_register, user=self.request.user, **form.cleaned_data)
		except ValidationError as error:
			form.add_error(None, error)
			return self.form_invalid(form)
		messages.success(self.request, "Gasto de caja registrado correctamente.")
		return super().form_valid(form)

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context["title"] = "Registrar gasto de caja"
		context["cash_register"] = self.cash_register
		return context


class CashRegisterDetailView(CashAccessMixin, DetailView):
	model = CashRegister
	template_name = "cash/detail.html"
	context_object_name = "cash_register"

	def get_queryset(self):
		queryset = CashRegister.objects.select_related("user", "branch").prefetch_related("movements")
		if self.request.user.role == User.ROLE_ADMIN:
			return queryset.filter(branch=self.request.user.branch)
		elif self.request.user.role == User.ROLE_SUPERADMIN:
			return queryset
		return queryset.filter(user=self.request.user)

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context["movements"] = self.object.movements.all()
		return context


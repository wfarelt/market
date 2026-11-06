from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, FormView, ListView, UpdateView

from apps.branches.models import Branch
from apps.users.models import User

from .forms import CashClosureCorrectionForm, CashRegisterCloseForm, CashRegisterOpenForm, ExpenseCategoryForm, PettyCashExpenseForm
from .models import CashRegister, ExpenseCategory
from .services import close_cash_register, correct_cash_closing, open_cash_register, register_petty_cash_expense


class CashAccessMixin(LoginRequiredMixin):
	def dispatch(self, request, *args, **kwargs):
		if request.user.role not in {User.ROLE_SUPERADMIN, User.ROLE_ADMIN, User.ROLE_CAJERO, User.ROLE_ALMACENERO}:
			raise Http404
		return super().dispatch(request, *args, **kwargs)


class ExpenseCategoryAccessMixin(CashAccessMixin):
	def dispatch(self, request, *args, **kwargs):
		if request.user.role not in {User.ROLE_SUPERADMIN, User.ROLE_ADMIN}:
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
			branch_id = self.request.GET.get("branch", "").strip()
			user_id = self.request.GET.get("user", "").strip()
			for value in (branch_id, user_id):
				if value and (
					not value.isascii()
					or not value.isdecimal()
					or len(value) > 19
					or int(value) > 9223372036854775807
				):
					return queryset.none()
			if branch_id:
				queryset = queryset.filter(branch_id=int(branch_id))
			if user_id:
				queryset = queryset.filter(user_id=int(user_id))
			return queryset
		if self.request.user.role == User.ROLE_SUPERADMIN:
			return queryset
		return queryset.filter(user=self.request.user)

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context["open_register"] = CashRegister.objects.filter(user=self.request.user, status=CashRegister.STATUS_OPEN).first()
		context["can_filter_cash_registers"] = self.request.user.role == User.ROLE_ADMIN
		if context["can_filter_cash_registers"]:
			context["branches"] = Branch.objects.order_by("name")
			context["selected_branch"] = self.request.GET.get("branch", "").strip()
			context["selected_user"] = self.request.GET.get("user", "").strip()
			users = User.objects.filter(cash_registers__isnull=False).distinct().order_by("username")
			selected_branch = context["selected_branch"]
			if selected_branch.isascii() and selected_branch.isdecimal() and len(selected_branch) <= 19:
				branch_id = int(selected_branch)
				if branch_id <= 9223372036854775807:
					users = users.filter(branch_id=branch_id)
			context["cash_register_users"] = users
		return context


class ExpenseCategoryListView(ExpenseCategoryAccessMixin, ListView):
	model = ExpenseCategory
	template_name = "cash/category_list.html"
	context_object_name = "categories"
	paginate_by = 20


class ExpenseCategoryCreateView(ExpenseCategoryAccessMixin, CreateView):
	model = ExpenseCategory
	form_class = ExpenseCategoryForm
	template_name = "cash/category_form.html"
	success_url = reverse_lazy("cash:category-list")

	def form_valid(self, form):
		form.instance.created_by = self.request.user
		messages.success(self.request, "Categoría de gasto creada correctamente.")
		return super().form_valid(form)

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context["title"] = "Nueva categoría de gasto"
		return context


class ExpenseCategoryUpdateView(ExpenseCategoryAccessMixin, UpdateView):
	model = ExpenseCategory
	form_class = ExpenseCategoryForm
	template_name = "cash/category_form.html"
	success_url = reverse_lazy("cash:category-list")

	def form_valid(self, form):
		messages.success(self.request, "Categoría de gasto actualizada correctamente.")
		return super().form_valid(form)

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context["title"] = "Editar categoría de gasto"
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


class CashClosureCorrectionView(LoginRequiredMixin, FormView):
	form_class = CashClosureCorrectionForm
	template_name = "cash/correction_form.html"

	def dispatch(self, request, *args, **kwargs):
		if request.user.role not in {User.ROLE_ADMIN, User.ROLE_SUPERADMIN}:
			raise Http404
		queryset = CashRegister.objects.select_related("user", "branch").filter(status=CashRegister.STATUS_CLOSED)
		if request.user.role == User.ROLE_ADMIN:
			queryset = queryset.filter(branch=request.user.branch)
		self.cash_register = get_object_or_404(queryset, pk=kwargs["pk"])
		return super().dispatch(request, *args, **kwargs)

	def get_initial(self):
		initial = super().get_initial()
		initial["closing_amount"] = self.cash_register.closing_amount
		return initial

	def get_success_url(self):
		return reverse_lazy("cash:detail", kwargs={"pk": self.cash_register.pk})

	def form_valid(self, form):
		try:
			correct_cash_closing(
				cash_register=self.cash_register,
				user=self.request.user,
				**form.cleaned_data,
			)
		except ValidationError as error:
			form.add_error(None, error)
			return self.form_invalid(form)
		messages.success(self.request, "Monto contado rectificado. El cierre original y su historial se conservaron.")
		return super().form_valid(form)

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
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
		queryset = CashRegister.objects.select_related("user", "branch").prefetch_related("movements", "corrections__created_by")
		if self.request.user.role == User.ROLE_ADMIN:
			return queryset.filter(branch=self.request.user.branch)
		elif self.request.user.role == User.ROLE_SUPERADMIN:
			return queryset
		return queryset.filter(user=self.request.user)

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context["movements"] = self.object.movements.all()
		context["corrections"] = self.object.corrections.all()
		context["can_correct_closing"] = (
			self.object.status == CashRegister.STATUS_CLOSED
			and self.request.user.role in {User.ROLE_ADMIN, User.ROLE_SUPERADMIN}
			and (self.request.user.role == User.ROLE_SUPERADMIN or self.object.branch_id == self.request.user.branch_id)
		)
		return context


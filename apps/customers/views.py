from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, FormView, ListView, UpdateView

from .forms import CreditPaymentForm, CustomerForm
from .models import Credit, Customer
from .permissions import CustomerManagementAccessMixin, CustomerReadPaymentAccessMixin
from .selectors import get_credits_list, get_customer_account_statement, get_customers_list
from .services import (
	create_customer,
	register_credit_payment,
	toggle_customer_active,
	update_customer,
)


class CustomerListView(CustomerReadPaymentAccessMixin, ListView):
	model = Customer
	template_name = "customers/customer_list.html"
	context_object_name = "customers"

	def get_queryset(self):
		query = self.request.GET.get("q", "").strip()
		return get_customers_list(self.request.user, query=query)

	def get_context_data(self, **kwargs):
		ctx = super().get_context_data(**kwargs)
		ctx["query"] = self.request.GET.get("q", "").strip()
		return ctx


class CustomerCreateView(CustomerManagementAccessMixin, CreateView):
	model = Customer
	form_class = CustomerForm
	template_name = "customers/customer_form.html"
	success_url = reverse_lazy("customers:list")

	def form_valid(self, form):
		try:
			create_customer(user=self.request.user, **form.cleaned_data)
		except ValidationError as error:
			for field, errors in error.message_dict.items():
				for err in errors:
					form.add_error(field if field in form.fields else None, err)
			return self.form_invalid(form)
		messages.success(self.request, "Cliente registrado correctamente.")
		return redirect(self.success_url)

	def get_context_data(self, **kwargs):
		ctx = super().get_context_data(**kwargs)
		ctx["title"] = "Nuevo Cliente"
		return ctx


class CustomerUpdateView(CustomerManagementAccessMixin, UpdateView):
	model = Customer
	form_class = CustomerForm
	template_name = "customers/customer_form.html"
	success_url = reverse_lazy("customers:list")

	def form_valid(self, form):
		try:
			update_customer(customer=self.object, data=form.cleaned_data)
		except ValidationError as error:
			for field, errors in error.message_dict.items():
				for err in errors:
					form.add_error(field if field in form.fields else None, err)
			return self.form_invalid(form)
		messages.success(self.request, "Cliente actualizado correctamente.")
		return redirect(self.success_url)

	def get_context_data(self, **kwargs):
		ctx = super().get_context_data(**kwargs)
		ctx["title"] = f"Editar Cliente – {self.object.full_name}"
		return ctx


class CustomerDetailView(CustomerReadPaymentAccessMixin, DetailView):
	model = Customer
	template_name = "customers/customer_detail.html"
	context_object_name = "customer"

	def get_context_data(self, **kwargs):
		ctx = super().get_context_data(**kwargs)
		statement = get_customer_account_statement(self.object, user=self.request.user)
		ctx.update(statement)
		return ctx


class CustomerToggleActiveView(CustomerManagementAccessMixin, DetailView):
	model = Customer

	def post(self, request, *args, **kwargs):
		customer = self.get_object()
		toggle_customer_active(customer=customer)
		status_str = "activado" if customer.is_active else "desactivado"
		messages.success(request, f"Cliente {customer.full_name} {status_str} correctamente.")
		return redirect("customers:list")


class CreditListView(CustomerReadPaymentAccessMixin, ListView):
	model = Credit
	template_name = "customers/credit_list.html"
	context_object_name = "credits"

	def get_queryset(self):
		filters = {
			"q": self.request.GET.get("q", "").strip(),
			"status": self.request.GET.get("status", "").strip(),
			"customer_id": self.request.GET.get("customer_id", "").strip(),
		}
		return get_credits_list(self.request.user, filters=filters)

	def get_context_data(self, **kwargs):
		ctx = super().get_context_data(**kwargs)
		ctx["q"] = self.request.GET.get("q", "").strip()
		ctx["status"] = self.request.GET.get("status", "").strip()
		ctx["statuses"] = Credit.STATUS_CHOICES
		return ctx


class CreditDetailView(CustomerReadPaymentAccessMixin, DetailView):
	model = Credit
	template_name = "customers/credit_detail.html"
	context_object_name = "credit"

	def get_queryset(self):
		return get_credits_list(self.request.user)


class CreditPaymentCreateView(CustomerReadPaymentAccessMixin, FormView):
	form_class = CreditPaymentForm
	template_name = "customers/credit_payment_form.html"

	def dispatch(self, request, *args, **kwargs):
		self.credit = get_object_or_404(
			get_credits_list(request.user),
			pk=kwargs["pk"],
		)
		return super().dispatch(request, *args, **kwargs)

	def form_valid(self, form):
		try:
			register_credit_payment(
				credit_pk=self.credit.pk,
				amount=form.cleaned_data["amount"],
				user=self.request.user,
				notes=form.cleaned_data.get("notes", ""),
			)
		except ValidationError as error:
			for err in error.messages:
				form.add_error(None, err)
			return self.form_invalid(form)
		messages.success(self.request, f"Pago registrado correctamente para el crédito {self.credit.number}.")
		return redirect("customers:credit-detail", pk=self.credit.pk)

	def get_context_data(self, **kwargs):
		ctx = super().get_context_data(**kwargs)
		ctx["credit"] = self.credit
		return ctx


class CustomerAccountStatementView(CustomerReadPaymentAccessMixin, DetailView):
	model = Customer
	template_name = "customers/account_statement.html"
	context_object_name = "customer"

	def get_context_data(self, **kwargs):
		ctx = super().get_context_data(**kwargs)
		statement = get_customer_account_statement(self.object, user=self.request.user)
		ctx.update(statement)
		return ctx


from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from apps.users.models import User
from .forms import TransferForm, TransferItemFormSet
from .models import Transfer
from .permissions import can_view_transfer
from .services import cancel_transfer, receive_transfer, send_transfer


class TransferAccessMixin(LoginRequiredMixin):
	def dispatch(self, request, *args, **kwargs):
		if request.user.role == User.ROLE_CAJERO or not request.user.is_authenticated:
			raise Http404
		return super().dispatch(request, *args, **kwargs)


class TransferListView(TransferAccessMixin, ListView):
	model = Transfer; template_name = "transfers/list.html"; context_object_name = "transfers"
	def get_queryset(self):
		qs = Transfer.objects.select_related("origin_branch", "destination_branch", "created_by")
		user = self.request.user
		if user.role not in {User.ROLE_ADMIN, User.ROLE_SUPERADMIN}: qs = qs.filter(origin_branch=user.branch_id) | qs.filter(destination_branch=user.branch_id)
		for field in ("status", "origin_branch", "destination_branch"):
			if value := self.request.GET.get(field): qs = qs.filter(**{f"{field}_id" if field.endswith("branch") else field: value})
		return qs


class TransferFormMixin(TransferAccessMixin):
	form_class = TransferForm; template_name = "transfers/form.html"
	def get_formset(self): return TransferItemFormSet(self.request.POST or None, instance=self.object)
	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs); context["formset"] = kwargs.get("formset") or self.get_formset(); return context
	def form_valid(self, form):
		formset = self.get_formset()
		formset.is_valid()
		valid_forms = [
			item_form for item_form in formset.forms
			if item_form.cleaned_data and not item_form.errors and not item_form.cleaned_data.get("DELETE")
		]
		if not valid_forms:
			formset._non_form_errors = formset.error_class(["Agrega al menos un producto válido."])
			return self.render_to_response(self.get_context_data(form=form, formset=formset))
		with transaction.atomic():
			self.object = form.save(commit=False)
			if not self.object.pk: self.object.created_by = self.request.user
			self.object.save()
			for item_form in formset.forms:
				if item_form.cleaned_data.get("DELETE") and item_form.instance.pk:
					item_form.instance.delete()
			for item_form in valid_forms:
				item = item_form.save(commit=False)
				item.transfer = self.object
				item.save()
		return redirect("transfers:detail", pk=self.object.pk)


class TransferCreateView(TransferFormMixin, CreateView):
	def get(self, *args, **kwargs): self.object = Transfer(); return super().get(*args, **kwargs)
	def post(self, *args, **kwargs): self.object = Transfer(); return super().post(*args, **kwargs)


class TransferUpdateView(TransferFormMixin, UpdateView):
	model = Transfer
	def get_object(self, queryset=None):
		obj = super().get_object(queryset)
		if obj.status != Transfer.STATUS_DRAFT or not can_view_transfer(self.request.user, obj): raise Http404
		return obj


class TransferDetailView(TransferAccessMixin, DetailView):
	model = Transfer; template_name = "transfers/detail.html"; context_object_name = "transfer"
	def get_queryset(self): return Transfer.objects.select_related("origin_branch", "destination_branch").prefetch_related("items__product")
	def get_object(self, queryset=None):
		obj = super().get_object(queryset)
		if not can_view_transfer(self.request.user, obj): raise Http404
		return obj


class TransferActionView(TransferAccessMixin, View):
	action = None
	def post(self, request, pk):
		transfer = get_object_or_404(Transfer, pk=pk)
		try:
			if self.action == "send": send_transfer(transfer, request.user)
			elif self.action == "receive": receive_transfer(transfer, request.user, {int(key.split("-")[-1]): value for key, value in request.POST.items() if key.startswith("item-")})
			else: cancel_transfer(transfer, request.user)
		except ValidationError as error: messages.error(request, "; ".join(error.messages))
		return redirect("transfers:detail", pk=pk)


class TransferSendView(TransferActionView): action = "send"
class TransferReceiveView(TransferActionView): action = "receive"
class TransferCancelView(TransferActionView): action = "cancel"


from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView

from apps.users.models import User

from .forms import StockInitialForm
from .models import Stock


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


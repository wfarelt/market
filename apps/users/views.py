from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import Http404
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView

from .forms import UserManagementCreationForm, UserManagementForm
from .models import User


class UserManagementAccessMixin(LoginRequiredMixin, UserPassesTestMixin):
	def test_func(self):
		return self.request.user.role in {User.ROLE_SUPERADMIN, User.ROLE_ADMIN}

	def can_manage(self, user):
		return self.request.user.role == User.ROLE_SUPERADMIN or (
			user.role != User.ROLE_SUPERADMIN and not user.is_superuser
		)


class UserListView(UserManagementAccessMixin, ListView):
	model = User
	template_name = "users/list.html"
	context_object_name = "users"

	def get_queryset(self):
		queryset = User.objects.select_related("branch").order_by("username")
		if self.request.user.role == User.ROLE_ADMIN:
			return queryset.exclude(role=User.ROLE_SUPERADMIN).exclude(is_superuser=True)
		return queryset


class UserCreateView(UserManagementAccessMixin, CreateView):
	form_class = UserManagementCreationForm
	template_name = "users/form.html"
	success_url = reverse_lazy("users:list")

	def get_form_kwargs(self):
		kwargs = super().get_form_kwargs()
		kwargs["actor"] = self.request.user
		return kwargs

	def form_valid(self, form):
		messages.success(self.request, "Usuario registrado correctamente.")
		return super().form_valid(form)

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context["title"] = "Nuevo usuario"
		return context


class UserUpdateView(UserManagementAccessMixin, UpdateView):
	model = User
	form_class = UserManagementForm
	template_name = "users/form.html"
	success_url = reverse_lazy("users:list")

	def get_object(self, queryset=None):
		user = super().get_object(queryset)
		if not self.can_manage(user):
			raise Http404
		return user

	def get_form_kwargs(self):
		kwargs = super().get_form_kwargs()
		kwargs["actor"] = self.request.user
		return kwargs

	def form_valid(self, form):
		messages.success(self.request, "Usuario actualizado correctamente.")
		return super().form_valid(form)

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context["title"] = f"Editar usuario: {self.object.username}"
		return context


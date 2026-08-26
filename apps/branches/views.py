from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView,
    DetailView,
    ListView,
    UpdateView,
)

from apps.users.models import User
from .forms import BranchForm
from .models import Branch


class BranchAccessMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.role in {User.ROLE_SUPERADMIN, User.ROLE_ADMIN}


class BranchListView(BranchAccessMixin, ListView):
    model = Branch
    template_name = "branches/list.html"
    context_object_name = "branches"


class BranchCreateView(BranchAccessMixin, CreateView):
    model = Branch
    form_class = BranchForm
    template_name = "branches/form.html"
    success_url = reverse_lazy("branches:list")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, "Sucursal creada correctamente.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = "Nueva sucursal"
        return ctx


class BranchUpdateView(BranchAccessMixin, UpdateView):
    model = Branch
    form_class = BranchForm
    template_name = "branches/form.html"
    success_url = reverse_lazy("branches:list")

    def form_valid(self, form):
        messages.success(self.request, "Sucursal actualizada correctamente.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = f"Editar – {self.object.name}"
        return ctx


class BranchDetailView(BranchAccessMixin, DetailView):
    model = Branch
    template_name = "branches/detail.html"
    context_object_name = "branch"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["users"] = self.object.users.all()
        return ctx


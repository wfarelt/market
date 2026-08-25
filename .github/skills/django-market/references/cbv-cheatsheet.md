# Django CBV Cheatsheet

## Common Base Classes

| Use Case | CBV | Key attributes |
|----------|-----|----------------|
| List objects | `ListView` | `model`, `template_name`, `context_object_name`, `paginate_by` |
| Show one object | `DetailView` | `model`, `template_name` |
| Create object | `CreateView` | `model`, `form_class`, `success_url` |
| Edit object | `UpdateView` | `model`, `form_class`, `success_url` |
| Delete object | `DeleteView` | `model`, `success_url` |

## Standard View Structure
```python
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views.generic import ListView, CreateView
from django.urls import reverse_lazy
from .models import MyModel
from .forms import MyModelForm

class MyModelListView(LoginRequiredMixin, ListView):
    model = MyModel
    template_name = 'myapp/list.html'
    context_object_name = 'object_list'
    paginate_by = 20

class MyModelCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = MyModel
    form_class = MyModelForm
    template_name = 'myapp/form.html'
    success_url = reverse_lazy('myapp:list')
    permission_required = 'myapp.add_mymodel'

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)
```

## Mixins Applied in Market

| Mixin | When |
|-------|------|
| `LoginRequiredMixin` | All views except public pages |
| `PermissionRequiredMixin` | Write operations (create, update, delete) |
| `UserPassesTestMixin` | Custom access logic (e.g. branch isolation) |

## Success Messages
```python
from django.contrib.messages.views import SuccessMessageMixin

class MyModelCreateView(SuccessMessageMixin, LoginRequiredMixin, CreateView):
    success_message = "Record created successfully."
```

## Overridable Methods (most common)
- `get_queryset()` — filter by branch, user, status
- `get_context_data(**kwargs)` — inject extra template context
- `form_valid(form)` — set auto fields before save
- `get_success_url()` — dynamic redirect after save

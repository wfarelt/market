---
name: django-market
description: 'Development skill for the Market project: Django 5, SQLite, Bootstrap 5. Use when implementing any feature, module, or architectural decision in this project. Triggers: new module, new model, new view, new form, new template, CRUD, architecture proposal, app setup, sales, inventory, purchases, reports, dashboard, users, branches, cash.'
argument-hint: 'Module name or feature to implement (e.g. "products CRUD" or "sales list view")'
---

# Django Market — Development Skill

## Stack
- **Backend**: Django 5
- **Database**: SQLite
- **Frontend**: Bootstrap 5
- **Architecture**: Modular Django apps

## Module Map

```
apps/
├── core/          # Shared base models, mixins, utilities
├── users/         # Authentication, roles, permissions
├── branches/      # Branch/location management
├── settings_app/  # Global business configuration
├── products/      # Product catalog, categories, units
├── inventory/     # Stock control, adjustments, movements
├── cash/          # Cash registers, sessions, openings/closings
├── sales/         # POS, invoices, sale lines
├── customers/     # Customer management, credit
├── purchases/     # Supplier orders, receiving, purchase lines
├── reports/       # Aggregated queries, exports
└── dashboard/     # KPIs, charts, summary views
```

## Core Principles

| Principle | Application |
|-----------|-------------|
| **SOLID** | One responsibility per class/function; depend on abstractions |
| **DRY** | Shared logic in `core`; no copy-paste across apps |
| **KISS** | Simplest solution that satisfies requirements |
| **Clean Architecture** | Business logic in models/services, not in views or templates |

## Mandatory Rules

1. **Never generate unsolicited code.** Only implement exactly what is requested.
2. **Work module by module.** Complete and validate one app before moving to the next.
3. **Propose architecture before coding.** Present model/URL/view/template structure and wait for approval.
4. **Maintain separation of responsibilities.** Views orchestrate; models contain business logic; templates only render.
5. **Prioritize maintainability and scalability.** Prefer explicit over implicit; avoid over-engineering.

---

## Workflow

### Step 1 — Understand the Request
- Identify the target module from the module map.
- Determine the scope: model, view, form, template, URL, service, or a combination.
- If the scope is ambiguous, ask one focused clarifying question before proceeding.

### Step 2 — Propose Architecture
Present a concise proposal containing only what is relevant:

```
Module: <app_name>
─────────────────────────────────────────
Models     : List fields, relationships, Meta
URLs       : Route names and paths
Views      : Class-based or function-based, mixins
Forms      : ModelForm or Form, validation notes
Templates  : Template names, blocks, Bootstrap components
Services   : Any business-logic helpers (if needed)
```

Wait for explicit user approval before writing any code.

### Step 3 — Implement
- Follow the approved proposal exactly.
- Place shared logic (mixins, base models, utilities) in `apps/core/`.
- Use Django's class-based views with appropriate mixins (`LoginRequiredMixin`, `PermissionRequiredMixin`, etc.).
- Bootstrap 5 for all UI — no custom CSS unless specifically requested.
- Each model must inherit from a `TimeStampedModel` base (in `core`) with `created_at` / `updated_at`.

### Step 4 — Validate
After implementation, verify:
- [ ] No business logic leaking into views or templates
- [ ] No duplicated code across apps
- [ ] URL names follow `<app>:<action>` convention (e.g., `products:list`)
- [ ] Templates extend a base layout and use named blocks
- [ ] Forms include CSRF token and Bootstrap form classes
- [ ] Migrations generated and consistent with models

### Step 5 — Report
Summarize only what was created/modified. No explanatory prose beyond what the user needs to continue.

---

## Conventions

### Models
```python
# Always inherit from core base
class Product(TimeStampedModel):
    ...
    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'products'
```

### URLs
```python
# apps/<app>/urls.py
app_name = '<app>'
urlpatterns = [
    path('', ListView.as_view(), name='list'),
    path('<int:pk>/', DetailView.as_view(), name='detail'),
    path('create/', CreateView.as_view(), name='create'),
    path('<int:pk>/update/', UpdateView.as_view(), name='update'),
    path('<int:pk>/delete/', DeleteView.as_view(), name='delete'),
]
```

### Templates
```
templates/
└── <app>/
    ├── list.html
    ├── detail.html
    ├── form.html
    └── confirm_delete.html
```

### Inter-app Imports
- `sales` may import from `products`, `customers`, `cash`, `inventory`.
- `reports` and `dashboard` are read-only consumers — they never write data.
- `core` has no imports from other apps.

---

## Reference Files

- [Module dependency map](./references/dependencies.md)
- [Bootstrap 5 component patterns](./references/bootstrap-patterns.md)
- [Django CBV cheatsheet](./references/cbv-cheatsheet.md)

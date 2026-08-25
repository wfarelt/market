---
name: erp-ui-standards
description: 'UI/UX standards for the Market ERP: modern SaaS style inspired by Stripe, Linear, Notion, Vercel. Use when designing or implementing any template, layout, component, form, dashboard, or navigation element. Triggers: template, layout, sidebar, navbar, form, table, dashboard, card, modal, UI, UX, Bootstrap, component, design, style, color, responsive.'
argument-hint: 'UI element or page to design (e.g. "product list table" or "sidebar navigation")'
---

# ERP UI Standards

## Design Philosophy

Modern, minimal SaaS. The interface should feel fast, focused, and uncluttered.

**Inspirations**: Stripe · Linear · Notion · Vercel

| Principle | Meaning in practice |
|-----------|---------------------|
| **Minimalist** | Show only what the user needs right now |
| **Responsive** | Mobile-first; works on tablet and desktop |
| **Fast** | No heavy animations; no unnecessary modals |
| **Simple** | One primary action per screen |
| **User-first** | Reduce clicks; surface the most-used actions |

---

## Layout

### Shell Structure
```
┌──────────────────────────────────────────┐
│  Topbar  (brand + user menu)             │
├──────────┬───────────────────────────────┤
│ Sidebar  │  Main Content Area            │
│ (collap- │  ┌──────────────────────────┐ │
│  sable)  │  │ Page Header (title + CTA)│ │
│          │  ├──────────────────────────┤ │
│          │  │ Content                  │ │
│          │  └──────────────────────────┘ │
└──────────┴───────────────────────────────┘
```

- Sidebar collapses to icon-only on mobile / on toggle.
- Active nav item uses a left accent border, not background fill.
- Topbar is sticky; sidebar scrolls independently.

### Spacing Scale (Bootstrap 5)
- Section padding: `p-4` / `py-3 px-4`
- Card padding: `p-4`
- Between sections: `mb-4`
- Between form fields: `mb-3`

---

## Color Usage

Use Bootstrap's semantic palette only. No custom colors unless absolutely required.

| Role | Class |
|------|-------|
| Primary action | `btn-primary` |
| Destructive action | `btn-danger` |
| Neutral / cancel | `btn-outline-secondary` |
| Success state | `text-success` / `badge bg-success` |
| Warning state | `text-warning` / `badge bg-warning text-dark` |
| Page background | `bg-body` (light gray, not pure white) |
| Card background | `bg-white` with `border-0 shadow-sm` |

**Rule:** Maximum 2 accent colors per screen. No decorative color.

---

## Typography

- Headings: `fw-semibold`, not bold.
- Page title: `h5` or `h4` — never `h1` inside content.
- Secondary text / labels: `text-muted small`.
- Monospace values (amounts, IDs): `font-monospace`.

---

## Components

### Page Header
```html
<div class="d-flex align-items-center justify-content-between mb-4">
  <h5 class="mb-0 fw-semibold">Page Title</h5>
  <a href="{% url 'app:create' %}" class="btn btn-primary btn-sm">+ New</a>
</div>
```

### Card
```html
<div class="card border-0 shadow-sm">
  <div class="card-body p-4">
    ...
  </div>
</div>
```

### Data Table
- Use `table-hover` + `align-middle`.
- Keep columns ≤ 6; hide secondary columns on mobile with `d-none d-md-table-cell`.
- Actions column: icon buttons only (`btn-sm btn-outline-*`), no text labels.
- Empty state: centered message + optional CTA, never an empty table.

### Forms
- One column by default; two columns only on `col-md-6` grids for simple fields.
- Labels above fields, not inline.
- No placeholder-as-label.
- Submit button: right-aligned on desktop, full-width on mobile.
- Inline validation errors (`.invalid-feedback`), not alert banners.

### Status Badges
```html
<span class="badge rounded-pill bg-success">Active</span>
<span class="badge rounded-pill bg-secondary">Draft</span>
<span class="badge rounded-pill bg-warning text-dark">Pending</span>
<span class="badge rounded-pill bg-danger">Cancelled</span>
```

### Modals
- Use only for **confirmations** (e.g., delete) and **quick-add** flows.
- Do not use modals for full forms (use a dedicated page instead).
- Always include a clear cancel action.

---

## Dashboard

- Lead with KPI cards (4 max per row).
- KPI card: large number + label + optional delta (`↑ 12%`).
- Charts only when data is time-series or comparative — no decorative charts.
- Keep the dashboard scannable in under 5 seconds.

```html
<!-- KPI Card pattern -->
<div class="card border-0 shadow-sm">
  <div class="card-body p-4">
    <p class="text-muted small mb-1">Total Sales</p>
    <h4 class="fw-semibold mb-0">$12,400</h4>
    <small class="text-success">↑ 8% this week</small>
  </div>
</div>
```

---

## What to Avoid

| Avoid | Reason |
|-------|--------|
| Overloaded screens | Cognitive overload; slows users down |
| Excessive color | Distracts; reduces trust |
| Complex multi-step forms on one page | Use wizards or separate pages instead |
| Full-page modals | Breaks navigation context |
| Decorative icons without labels on primary actions | Accessibility and clarity |
| `table-bordered` with heavy cell borders | Feels dated and cluttered |
| Success/error alerts that stay permanently | Auto-dismiss after 4s or use inline |

---

## Template Inheritance

```
templates/
├── base.html              ← shell: topbar + sidebar + content slot
├── partials/
│   ├── _sidebar.html
│   ├── _topbar.html
│   ├── _messages.html     ← auto-dismissing alerts
│   └── _pagination.html
└── <app>/
    ├── list.html
    ├── form.html
    ├── detail.html
    └── confirm_delete.html
```

Every page extends `base.html` and fills `{% block content %}` only.

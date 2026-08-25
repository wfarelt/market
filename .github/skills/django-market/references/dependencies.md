# Module Dependency Map

Arrows indicate allowed import direction (`→` = "may import from").

```
core          ← (no imports from other apps)
users         → core
branches      → core, users
settings_app  → core, users
products      → core, categories (internal)
inventory     → core, products, branches
cash          → core, users, branches
customers     → core, users
purchases     → core, products, suppliers (internal), branches
sales         → core, products, customers, cash, inventory, branches
reports       → core, sales, purchases, inventory, cash (read-only)
dashboard     → core, sales, purchases, inventory, cash (read-only)
```

## Rules
- `reports` and `dashboard` never call `.save()`, `.create()`, or `.delete()`.
- Cross-app FK references use `settings.AUTH_USER_MODEL` for users.
- Circular imports are forbidden; use string references in ForeignKey when needed.

---
name: grocery-business-rules
description: 'Business rules for the Market grocery system: multi-branch, single company. Use when designing or implementing models, logic, or workflows related to stock, inventory, kardex, transfers, cash register, sales POS, credits, purchases, or any rule that governs how data flows between branches. Triggers: stock, kardex, transfer, traspaso, cash, caja, sale, venta, credit, purchase, inventory, branch.'
argument-hint: 'Module or rule to clarify (e.g. "kardex movement" or "transfer states")'
---

# Grocery Business Rules

## Business Context

Single company, multiple branches. Each branch is fully independent in terms of inventory, cash, and sales. No shared stock across branches.

---

## Branch Isolation

| Resource | Scope |
|----------|-------|
| Stock | Per branch (never global) |
| Cash register | Per branch / per shift |
| Sales | Per branch |
| Purchases | Per branch |

---

## Stock Rules

- **Stock is never stored on `Product`.**
- Stock lives in a join between `Product` + `Branch` (e.g., `Inventory` or `Stock` model).
- Every stock change — whether from a sale, purchase, adjustment, or transfer — **must generate a Kardex entry**.

### Kardex Movement Types

| Type | Spanish | Effect |
|------|---------|--------|
| Entry | Ingreso | Increases stock |
| Exit | Egreso | Decreases stock |
| Transfer out | Traspaso salida | Decreases stock at origin branch |
| Transfer in | Traspaso entrada | Increases stock at destination branch |

---

## Transfers (Traspasos)

Transfers move stock from one branch to another. They have a lifecycle:

```
Draft → Sent → Received
              ↘ Cancelled
```

| State | Description |
|-------|-------------|
| `Draft` | Created, not yet dispatched |
| `Sent` | Dispatched from origin; stock deducted at origin |
| `Received` | Confirmed at destination; stock added at destination |
| `Cancelled` | Annulled; stock reversal applied if already `Sent` |

**Rule:** Stock at destination is only credited on `Received`, never on `Sent`.

---

## Sales Rules

A completed sale must:
1. Deduct stock for each line item (generates Kardex `Egreso`).
2. Register a cash movement in the active cash register session of that branch.

No sale is valid if:
- There is no open cash register for the branch.
- Stock is insufficient for any line item.

---

## Cash Register (Caja) Rules

- One cash register session per **shift**.
- Only **one open session per user** at any time.
- A session requires explicit **opening** (with opening amount) and **closing** (with counted amount).
- Sales, refunds, and manual movements are registered against the active session.

```
Opening → [sales / movements] → Closing
```

---

## Module Rules Summary

| Module | Key Constraint |
|--------|---------------|
| **Products** | No stock field; catalog only |
| **Inventory** | Stock = Product + Branch; all changes via Kardex |
| **Transfers** | State machine; stock moves on Sent/Received |
| **Cash (Caja)** | One open session per user; opening/closing mandatory |
| **Sales POS** | Requires open cash session; deducts stock on confirm |
| **Customers** | Linked to sales; optional credit account |
| **Credits** | Balance per customer; decremented on payment |
| **Purchases** | Receiving generates Kardex `Ingreso` at branch |
| **Reports** | Read-only; aggregates from all other modules |

---

## Invariants (Never Violate)

1. `Product.stock` does not exist — query `Inventory` for stock.
2. Every stock mutation → one `Kardex` record.
3. A sale cannot be posted without an active `CashSession`.
4. A transfer's destination stock changes only on `Received`.
5. Cancelling a `Sent` transfer must reverse the origin Kardex entry.
6. One `CashSession` open per user — enforced at application level.

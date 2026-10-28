# Architecture

```
                 Phone / visitors (browser)
                            │ HTTPS :443
                  ┌─────────▼─────────┐
                  │      Caddy        │  automatic HTTPS, security headers
                  └───┬───────────┬───┘
             /api/*   │           │  everything else
          ┌───────────▼──┐   ┌────▼───────────────┐
          │   FastAPI    │◄──┤      Next.js       │  public site (server-rendered)
          │   (api)      │   │                    │  + /dashboard (client pages)
          └──┬────────┬──┘   └────────────────────┘
             │        │
   files ◄───┘        │ SQL
 (private volume)┌────▼───────┐
                 │ PostgreSQL │◄─────────────┐
                 └────────────┘              │ SQL
                                     ┌───────┴────────┐
                                     │    worker      │  APScheduler jobs
                                     │ (same Python)  │  + message dispatcher
                                     └───┬────────┬───┘  + WhatsApp health check
                POST /send, GET /status  │        │ email if WhatsApp down 5+ min
              (internal network + token) │        ▼
                                   ┌─────▼──────┐  Gmail SMTP
                                   │ whatsapp   │
                                   │ (Baileys)  │  session volume
                                   └────────────┘
```

Only Caddy is reachable from the internet.

## Key decisions

| Decision | Why |
|---|---|
| **Outbox pattern** for WhatsApp | A change and its notification are saved in the same DB transaction (`message_log`, status `pending`). The worker sends them one at a time with 8–20 s random gaps. Nothing is lost if WhatsApp is down; rate limiting lives in one place. |
| **`dedupe_key` UNIQUE** | e.g. `rent_reminder:42:2026-11-05`. Jobs can run any number of times (restarts, catch-up) without double-sending. |
| Mark `sending` **before** the HTTP call | If the worker dies mid-send the row becomes `unknown` and is *not* auto-retried (a missed message beats a duplicate). |
| Reminders rebuilt at send time | If a tenant pays after the reminder was queued, it's skipped. |
| Separate **worker** process | Jobs never run twice even with several API processes; API restarts don't interrupt sending. |
| **DB sessions** in an httpOnly cookie | Revocable (logout everywhere on password change), not readable by JavaScript. Argon2 password hashing. |
| Same origin for site + API | Caddy (prod) / Next rewrites (dev) → no CORS, cookies just work. Origin check blocks cross-site writes (CSRF). |
| Private files on local disk | Random names, type detected from file bytes, served only to logged-in staff. Public gallery files in a separate folder. Swappable for S3 later (`app/storage.py`). |
| Money as integer rupees | No floating-point rounding errors. |

## Data model

```
users ─┬─ sessions
       └─ (Part 2) tenants.user_id
room_categories ─┬─ category_rates (sharing 1..N → monthly_rent, NULL = manual)
                 └─ rooms (number, floor)
tenants (room, sharing, rent_override, deposit_amount/collected, status, dates…)
   ├─ tenant_documents
   ├─ rent_records (one per month: amount_due, amount_paid, status)  ── payments
   └─ settlements ── settlement_deductions
audit_log      every change (kept after deletes)
message_log    WhatsApp outbox + history
site_settings  public website content       app_settings  owner number, payment note, health state
gallery_items  photos / videos
```

## Part 2 readiness (tenant portal)

- A tenant login = a `users` row with `role=tenant`, linked via `tenants.user_id` (column exists, unique).
- All staff routes already require `owner`/`admin` (`require_staff`) — tenants get 403.
- Tenant routes will filter by the logged-in tenant's id; roommate view returns name + room only.
- Complaints: new `complaints` table + `notify_owner()` (already exists) for WhatsApp alerts.

## Code map

```
backend/app/
  main.py                FastAPI app, CSRF origin check, routers
  core/                  config (.env), db, security, IST date helpers, phone format
  models/                SQLAlchemy tables
  schemas.py             request/response validation (Pydantic)
  api/routes/            auth, tenants (+documents, settlement), rent, rooms, messages, site, dashboard
  services/              business rules: rent.py, tenants.py, reminders.py, audit.py
  messaging/             outbox, message templates, WhatsApp client, email
  worker/                scheduler (main.py), jobs.py, dispatcher.py
  cli.py                 seed, create-user, set-password
frontend/src/
  app/page.tsx, gallery/ public site (server components)
  app/login, app/dashboard/…  owner UI (client components)
  components/            UI kit, TenantForm, PaymentModal, public layout
  lib/                   api client, types, formatting
whatsapp/src/index.ts    Baileys connection + /send /status /logout
```

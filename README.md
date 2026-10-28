# PG Manager

Owner dashboard + public website for a PG (paying guest) building: tenants, rent tracking,
a tick-to-mark-paid checklist, automatic WhatsApp rent reminders, and a public website.

**No personal data lives in this repository.** The PG's name, address, phone numbers, rent
rates and tenants are all entered in the dashboard after setup (stored in the database).
Logins are created with a command on the server, and secrets go in a git-ignored `.env`.

| Folder | What | Tech |
|---|---|---|
| `frontend/` | Public website + owner dashboard (mobile-first) | Next.js 16, TypeScript, Tailwind |
| `backend/` | API, rent logic, scheduled jobs (worker) | FastAPI, SQLAlchemy, Alembic, APScheduler |
| `whatsapp/` | Internal WhatsApp sender (QR login) | Node 22+, Baileys |
| `scripts/` | Backup / restore | bash, gpg, rclone |
| `docs/` | [Architecture](docs/ARCHITECTURE.md) · [Deployment](docs/DEPLOYMENT.md) | |

---

## Run it on your PC (Windows)

Needs Docker Desktop, Python 3.12+, Node 22.18+. All commands from the project folder.

### First time only

```powershell
# 1. Database (runs in Docker on port 5433)
docker compose -f docker-compose.dev.yml up -d

# 2. Backend packages
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # if blocked: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
pip install -r requirements-dev.txt

# 3. Create tables, rooms (55) and default content
alembic upgrade head
python -m app.cli seed

# 4. Logins (asks for a password each)
python -m app.cli create-user --email owner@example.com --name "Owner Name" --role owner --alerts
python -m app.cli create-user --email admin@example.com --name "Admin Name" --role admin   # optional
cd ..

# 5. Frontend + WhatsApp packages
cd frontend; npm install; cd ..
cd whatsapp; npm install; cd ..
```

### Every time — 4 terminals

| Terminal | Command | URL |
|---|---|---|
| 1 · API | `cd backend; .\.venv\Scripts\Activate.ps1; uvicorn app.main:app --reload` | http://localhost:8000/api/docs |
| 2 · Website | `cd frontend; npm run dev` | http://localhost:3000 |
| 3 · Worker (jobs + sending) | `cd backend; .\.venv\Scripts\Activate.ps1; python -m app.worker.main` | — |
| 4 · WhatsApp (optional) | `cd whatsapp; npm run dev` | QR on Dashboard → WhatsApp |

Dashboard: http://localhost:3000/dashboard

### First-time setup in the app

1. **More → Website**: PG name, address, phone, WhatsApp number, Google Maps link, food, amenities.
2. **More → Settings**: owner's WhatsApp number (gets alerts) and payment details for reminders (e.g. UPI id).
3. **More → Rates**: rent per room category and sharing type.
4. **Tenants → + Add tenant**.

The rooms (floors 2–6, 55 rooms) come from `python -m app.cli seed` — edit `backend/app/cli.py` to match another building.

> ⚠️ If you link a real WhatsApp number on your PC **and** run the worker, real messages go to real tenants. Use test tenants with your own numbers while developing.

### Tests

```powershell
cd backend; .\.venv\Scripts\Activate.ps1; pytest -q      # 24 tests, uses a separate pgapp_test database
cd frontend; npm run build                               # type-checks every page
cd whatsapp; npm run typecheck
```

### Database changes

Edit a model in `backend/app/models/`, then:

```powershell
alembic revision --autogenerate -m "describe the change"   # creates a migration file — review it
alembic upgrade head
```

In production, migrations run automatically when the API container starts.

---

## How it behaves (quick reference)

- **Rent** = category rate for the tenant's room + sharing type, unless a **custom rent** is set (shown with a purple "custom" badge).
- **Joining mid-month** → first month prorated by days (can be set manually on the form).
- **Room/sharing change mid-month** → this month prorated from today (or set manually); next months use the new rent.
- **Rate change** → by default current tenants keep their old rent; tick "apply to current tenants" to change everyone.
- **Capacity**: a room never holds more than its category max, nor more people than the smallest sharing type of anyone in it.
- **Records** for each month are created automatically on the 1st (and whenever the dashboard opens).
- **Reminders**: 5th–8th at 5 PM to Active + On-notice tenants owing rent or deposit, showing the total due. Unsent ones expire at 9 PM.
- **Owner report**: 9th at 10 AM, list of everyone not fully paid.
- **Change alerts**: every add/edit/payment/vacate/delete → WhatsApp to the owner, saying who made it.
- **No double sends**: every scheduled message has a unique key in the database; restarts are safe.
- **WhatsApp down** → messages wait and retry; after 5 minutes an email goes to the owner, plus a red banner in the dashboard.
- Schedules and pacing are set in `.env` (`REMINDER_DAYS`, `REMINDER_TIME`, `WA_MIN_DELAY_SECONDS` …).

from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.core.phone import normalize_phone
from app.core.timeutil import days_in_month, month_start, prorate, today_ist
from app.models import MessageLog, RentRecord
from app.models.enums import MessageKind, MessageStatus
from app.services.fmt import inr
from app.services.reminders import queue_owner_report, queue_rent_reminders

TODAY = today_ist()
MONTH = month_start(TODAY)


# ---------- helpers ----------


def room_id(client, number: str) -> int:
    return next(r["id"] for r in client.get("/api/rooms").json() if r["number"] == number)


def set_rates(client, category: str, rates: dict[int, int | None], apply_to_existing=False):
    cat = next(c for c in client.get("/api/categories").json() if c["name"] == category)
    r = client.put(
        f"/api/categories/{cat['id']}",
        json={
            "rates": [{"sharing": s, "monthly_rent": v} for s, v in rates.items()],
            "apply_to_existing": apply_to_existing,
        },
    )
    assert r.status_code == 200, r.text
    return r.json()


def add_tenant(client, name, room, sharing, joining=None, **extra):
    body = {
        "name": name,
        "phone": extra.pop("phone", "98765 43210"),
        "room_id": room_id(client, room),
        "sharing": sharing,
        "joining_date": (joining or MONTH - timedelta(days=40)).isoformat(),
        "deposit_amount": extra.pop("deposit_amount", 10000),
        **extra,
    }
    return client.post("/api/tenants", json=body)


def owner_messages(db) -> list[str]:
    return [
        m.body
        for m in db.scalars(
            select(MessageLog).where(MessageLog.kind == MessageKind.owner_change).order_by(MessageLog.id)
        )
    ]


@pytest.fixture
def rates(client):
    set_rates(client, "Standard (no balcony)", {1: 12000, 2: 9000, 3: 7000})
    set_rates(client, "Standard (balcony)", {1: 13000, 2: 10000, 3: 8000})


# ---------- pure helpers ----------


def test_phone_and_money_formatting():
    assert normalize_phone("98765 43210") == "919876543210"
    assert normalize_phone("+91-9876543210") == "919876543210"
    assert normalize_phone("09876543210") == "919876543210"
    with pytest.raises(ValueError):
        normalize_phone("12345")
    assert inr(6000) == "₹6,000"
    assert inr(150000) == "₹1,50,000"
    assert prorate(9000, date(2026, 11, 16)) == round(9000 * 15 / 30)


# ---------- auth ----------


def test_auth_required(anon):
    assert anon.get("/api/tenants").status_code == 401
    assert anon.post("/api/auth/login", json={"email": "owner@example.com", "password": "nope"}).status_code == 401
    assert anon.get("/api/public/site").status_code == 200


def test_cross_site_post_blocked(client):
    r = client.post("/api/auth/logout", headers={"Origin": "https://evil.example"})
    assert r.status_code == 403


# ---------- tenants & capacity ----------


def test_create_tenant_full_month_for_existing_tenant(client, rates):
    r = add_tenant(client, "Asha", "201", 3)
    assert r.status_code == 201, r.text
    t = r.json()
    assert t["rent"] == 7000 and t["rent_override"] is None
    assert t["deposit_collected"] == 10000  # defaults to full
    assert [rr["amount_due"] for rr in t["rent_records"]] == [7000]


def test_new_joiner_is_prorated(client, rates):
    joining = MONTH + timedelta(days=min(14, days_in_month(MONTH) - 1))
    t = add_tenant(client, "Bina", "201", 3, joining=joining).json()
    if joining <= TODAY:
        assert t["rent_records"][0]["amount_due"] == prorate(7000, joining)


def test_first_month_rent_can_be_set_manually(client, rates):
    t = add_tenant(client, "Chitra", "201", 3, joining=MONTH, first_month_rent=5000).json()
    assert t["rent_records"][0]["amount_due"] == 5000


def test_room_capacity_rules(client, rates):
    for name in ("A", "B", "C"):
        assert add_tenant(client, name, "202", 3).status_code == 201
    r = add_tenant(client, "D", "202", 3)
    assert r.status_code == 400 and "full" in r.json()["detail"]

    # A Double-sharing tenant can't be the 3rd person in a room
    assert add_tenant(client, "E", "203", 3).status_code == 201
    assert add_tenant(client, "F", "203", 3).status_code == 201
    r = add_tenant(client, "G", "203", 2)
    assert r.status_code == 400 and "Double" in r.json()["detail"]

    # Single needs an empty room
    r = add_tenant(client, "H", "203", 1)
    assert r.status_code == 400
    # Standard rooms max 3-sharing
    r = add_tenant(client, "I", "204", 4)
    assert r.status_code == 400


def test_sixth_floor_needs_custom_rent(client, rates):
    r = add_tenant(client, "Big", "601", 5)
    assert r.status_code == 400 and "No default rent" in r.json()["detail"]
    r = add_tenant(client, "Big", "601", 5, rent_override=6000)
    assert r.status_code == 201 and r.json()["rent"] == 6000


def test_update_room_and_sharing_notifies_owner_with_diff(client, rates, db):
    t = add_tenant(client, "Ravi", "201", 3).json()
    r = client.patch(f"/api/tenants/{t['id']}", json={"room_id": room_id(client, "401"), "sharing": 2})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["rent"] == 10000
    # Mid-month change: this month's due is prorated between old and new rent
    expected = 7000 + round((10000 - 7000) * (days_in_month(TODAY) - TODAY.day + 1) / days_in_month(TODAY))
    assert body["rent_records"][0]["amount_due"] == expected

    msg = owner_messages(db)[-1]
    assert "Room: 201 → 401" in msg
    assert "Sharing: Triple → Double" in msg
    assert "Rent: ₹7,000 → ₹10,000" in msg


def test_manual_current_month_due_on_change(client, rates):
    t = add_tenant(client, "Sita", "201", 3).json()
    r = client.patch(
        f"/api/tenants/{t['id']}",
        json={"room_id": room_id(client, "402"), "sharing": 2, "current_month_due": 7000},
    )
    assert r.json()["rent_records"][0]["amount_due"] == 7000


def test_override_shown(client, rates, db):
    t = add_tenant(client, "Meena", "201", 3).json()
    r = client.patch(f"/api/tenants/{t['id']}", json={"rent_override": 6500, "current_month_due": 7000})
    assert r.json()["rent"] == 6500 and r.json()["default_rent"] == 7000
    assert "(custom)" in owner_messages(db)[-1]
    r = client.patch(f"/api/tenants/{t['id']}", json={"rent_override": None, "current_month_due": 7000})
    assert r.json()["rent"] == 7000 and r.json()["rent_override"] is None


def test_rate_change_keeps_existing_tenants(client, rates):
    t = add_tenant(client, "Old", "201", 3).json()
    set_rates(client, "Standard (no balcony)", {3: 7500})
    assert client.get(f"/api/tenants/{t['id']}").json()["rent"] == 7000  # locked at old rate
    t2 = add_tenant(client, "New", "201", 3).json()
    assert t2["rent"] == 7500


# ---------- payments ----------


def test_partial_then_full_payment(client, rates):
    t = add_tenant(client, "Pay", "201", 3).json()
    rec = t["rent_records"][0]
    p = {"rent_record_id": rec["id"], "paid_on": TODAY.isoformat(), "mode": "upi"}
    r = client.post("/api/payments", json={**p, "amount": 3000})
    assert r.json()["status"] == "partial" and r.json()["balance"] == 4000
    assert client.post("/api/payments", json={**p, "amount": 5000}).status_code == 400  # overpay
    r = client.post("/api/payments", json={**p, "amount": 4000})
    assert r.json()["status"] == "paid"
    # Removing a payment reopens the balance
    pid = r.json()["payments"][-1]["id"]
    assert client.delete(f"/api/payments/{pid}").json()["status"] == "partial"


def test_checklist_tick_and_untick(client, rates, db):
    t = add_tenant(client, "Tick", "201", 3).json()
    rec = t["rent_records"][0]
    # Partial payment entered with details first
    client.post(
        "/api/payments",
        json={"rent_record_id": rec["id"], "amount": 2000, "paid_on": TODAY.isoformat(), "mode": "cash"},
    )
    # Tick pays the remaining balance
    r = client.post(f"/api/rent-records/{rec['id']}/mark-paid", json={"mode": "upi"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "paid" and r.json()["payments"][-1]["amount"] == 5000
    assert "₹5,000 via UPI" in owner_messages(db)[-1]
    assert client.post(f"/api/rent-records/{rec['id']}/mark-paid", json={}).status_code == 400
    # Untick removes only the checklist payment
    r = client.post(f"/api/rent-records/{rec['id']}/unmark-paid")
    assert r.json()["status"] == "partial" and r.json()["amount_paid"] == 2000
    # Nothing left to untick: the detailed payment stays
    assert client.post(f"/api/rent-records/{rec['id']}/unmark-paid").status_code == 400


def test_older_dues_carry_over(client, rates):
    t = add_tenant(client, "Due", "201", 3).json()
    prev = MONTH - timedelta(days=1)
    r = client.post(
        f"/api/tenants/{t['id']}/rent-records",
        json={"month": prev.strftime("%Y-%m"), "amount_due": 7000},
    )
    assert r.status_code == 201, r.text
    assert client.get(f"/api/tenants/{t['id']}").json()["outstanding"] == 14000


# ---------- reminders & reports ----------


def test_reminders_are_deduplicated_and_skip_paid(client, rates, db):
    unpaid = add_tenant(client, "Unpaid Girl", "201", 3, phone="9000000001").json()
    paid = add_tenant(client, "Paid Girl", "202", 3, phone="9000000002").json()
    rec = paid["rent_records"][0]
    client.post(
        "/api/payments",
        json={"rent_record_id": rec["id"], "amount": 7000, "paid_on": TODAY.isoformat(), "mode": "cash"},
    )
    assert queue_rent_reminders(db, TODAY) == 1
    db.commit()
    assert queue_rent_reminders(db, TODAY) == 0  # second run: nothing new
    db.commit()
    msg = db.scalar(select(MessageLog).where(MessageLog.kind == MessageKind.rent_reminder))
    assert msg.tenant_id == unpaid["id"]
    assert "Total due: ₹7,000" in msg.body


def test_deposit_balance_in_reminder(client, rates, db):
    t = add_tenant(client, "Dep", "201", 3, deposit_collected=4000).json()
    assert t["deposit_balance"] == 6000
    rec = t["rent_records"][0]
    client.post(
        "/api/payments",
        json={"rent_record_id": rec["id"], "amount": 7000, "paid_on": TODAY.isoformat(), "mode": "cash"},
    )
    assert queue_rent_reminders(db, TODAY) == 1
    db.commit()
    body = db.scalar(select(MessageLog.body).where(MessageLog.kind == MessageKind.rent_reminder))
    assert "deposit balance: ₹6,000" in body


def test_owner_report_once_per_month(client, rates, db):
    add_tenant(client, "Late", "201", 3)
    assert queue_owner_report(db, TODAY) is True
    db.commit()
    assert queue_owner_report(db, TODAY) is False
    body = db.scalar(select(MessageLog.body).where(MessageLog.kind == MessageKind.owner_report))
    assert "Late — Room 201" in body


def test_dispatcher_sends_and_skips_paid(client, rates, db, monkeypatch):
    from app.messaging import whatsapp_client
    from app.worker import dispatcher

    sent = []
    monkeypatch.setattr(whatsapp_client, "send_text", lambda phone, text: sent.append((phone, text)))
    a = add_tenant(client, "Alpha", "201", 3, phone="9000000011").json()
    add_tenant(client, "Beta", "202", 3, phone="9000000012")
    queue_rent_reminders(db, TODAY)
    db.commit()
    # Alpha pays after the reminder was queued but before it's sent
    client.post(
        "/api/payments",
        json={
            "rent_record_id": a["rent_records"][0]["id"],
            "amount": 7000,
            "paid_on": TODAY.isoformat(),
            "mode": "cash",
        },
    )
    dispatcher.dispatch_pending()
    reminder_phones = [p for p, text in sent if "gentle reminder" in text]
    assert reminder_phones == ["919000000012"]
    db.expire_all()
    statuses = {m.tenant_id: m.status for m in db.scalars(select(MessageLog).where(MessageLog.kind == MessageKind.rent_reminder))}
    assert statuses[a["id"]] == MessageStatus.skipped


def test_dispatcher_retries_when_whatsapp_down(client, rates, db, monkeypatch):
    from app.messaging import whatsapp_client
    from app.worker import dispatcher

    def down(phone, text):
        raise whatsapp_client.WhatsAppError("not connected", retriable=True)

    monkeypatch.setattr(whatsapp_client, "send_text", down)
    add_tenant(client, "Gamma", "201", 3)
    queue_rent_reminders(db, TODAY)
    db.commit()
    dispatcher.dispatch_pending()
    db.expire_all()
    first, *rest = db.scalars(select(MessageLog).order_by(MessageLog.id)).all()
    # First message failed and is scheduled for a retry; the run stopped there
    assert first.status == MessageStatus.pending and first.attempts == 1
    assert all(m.status == MessageStatus.pending and m.attempts == 0 for m in rest)


# ---------- move-out ----------


def test_settlement(client, rates):
    t = add_tenant(client, "Leaving", "201", 3, deposit_amount=10000).json()
    preview = client.get(f"/api/tenants/{t['id']}/settlement/preview").json()
    assert preview["pending_dues"] == 7000
    r = client.post(
        f"/api/tenants/{t['id']}/settlement",
        json={"move_out_date": TODAY.isoformat(), "deductions": [{"reason": "Painting", "amount": 1000}]},
    )
    assert r.status_code == 200, r.text
    assert r.json()["refund_amount"] == 10000 - 7000 - 1000
    t = client.get(f"/api/tenants/{t['id']}").json()
    assert t["status"] == "vacated"
    # Bed is free again
    for name in ("X", "Y", "Z"):
        assert add_tenant(client, name, "201", 3).status_code == 201


def test_delete_requires_exact_name(client, rates, db):
    t = add_tenant(client, "Delete Me", "201", 3).json()
    assert client.delete(f"/api/tenants/{t['id']}", params={"confirm_name": "wrong"}).status_code == 400
    assert client.delete(f"/api/tenants/{t['id']}", params={"confirm_name": "Delete Me"}).status_code == 204
    assert client.get(f"/api/tenants/{t['id']}").status_code == 404
    assert db.scalar(select(RentRecord)) is None
    assert "deleted permanently" in owner_messages(db)[-1]


# ---------- documents ----------


PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100


def test_documents_private(client, anon, rates):
    t = add_tenant(client, "Docs", "201", 3).json()
    r = client.post(
        f"/api/tenants/{t['id']}/documents",
        data={"kind": "photo"},
        files={"file": ("me.png", PNG, "image/png")},
    )
    assert r.status_code == 201, r.text
    doc_id = r.json()["id"]
    bad = client.post(
        f"/api/tenants/{t['id']}/documents",
        data={"kind": "id_proof"},
        files={"file": ("evil.pdf", b"<script>alert(1)</script>", "application/pdf")},
    )
    assert bad.status_code == 400
    assert client.get(f"/api/tenants/{t['id']}/documents/{doc_id}").content == PNG
    assert anon.get(f"/api/tenants/{t['id']}/documents/{doc_id}").status_code == 401
    assert anon.get("/api/public/media/../private/tenants").status_code in (400, 404)


def test_dashboard_and_month_view(client, rates):
    add_tenant(client, "Dash", "201", 3)
    d = client.get("/api/dashboard").json()
    assert d["rent"]["expected"] == 7000 and d["rent"]["unpaid"] == 1
    assert d["unpaid"][0]["name"] == "Dash"
    m = client.get("/api/rent", params={"month": MONTH.strftime("%Y-%m")}).json()
    assert m["pending"] == 7000 and m["rows"][0]["room_number"] == "201"

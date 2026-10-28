"""Admin commands.

    python -m app.cli seed                 # room categories + 55 rooms (PG details are entered in the app)
    python -m app.cli create-user --email you@example.com --name "Your Name" --role owner --alerts
    python -m app.cli set-password --email you@example.com
"""

import argparse
import getpass
import os
import sys

from sqlalchemy import func, select

from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models import CategoryRate, Room, RoomCategory, User
from app.models.enums import Role

# name, description, max sharing, sort order
CATEGORIES = [
    ("Standard (no balcony)", "Floors 2–3", 3, 1),
    ("Standard (balcony)", "Floors 4–5, with balcony", 3, 2),
    ("Large room", "Rooms 210, 310, 410, 510 — bigger rooms", 4, 3),
    ("6th floor", "Rooms 601–603 — spacious rooms", 5, 4),
]

LARGE_ROOMS = {"210", "310", "410", "510"}



def _category_for(number: str, floor: int, cats: dict[str, RoomCategory]) -> RoomCategory:
    if floor == 6:
        return cats["6th floor"]
    if number in LARGE_ROOMS:
        return cats["Large room"]
    return cats["Standard (no balcony)"] if floor in (2, 3) else cats["Standard (balcony)"]


def seed() -> None:
    with SessionLocal() as db:
        cats = {c.name: c for c in db.scalars(select(RoomCategory)).all()}
        for name, desc, max_sharing, order in CATEGORIES:
            if name not in cats:
                cat = RoomCategory(name=name, description=desc, max_sharing=max_sharing, sort_order=order)
                cat.rates = [CategoryRate(sharing=s, monthly_rent=None) for s in range(1, max_sharing + 1)]
                db.add(cat)
                cats[name] = cat
        db.flush()

        existing = set(db.scalars(select(Room.number)).all())
        numbers = [(f"{f}{r:02d}", f) for f in (2, 3, 4, 5) for r in range(1, 14)]
        numbers += [(f"6{r:02d}", 6) for r in range(1, 4)]
        added = 0
        for number, floor in numbers:
            if number not in existing:
                db.add(Room(number=number, floor=floor, category=_category_for(number, floor, cats)))
                added += 1

        db.commit()
        print(f"Seed complete: {len(cats)} categories, {added} new rooms.")


def _read_password() -> str:
    if pw := os.environ.get("NEW_PASSWORD"):  # non-interactive use (scripts)
        if len(pw) < 8:
            sys.exit("NEW_PASSWORD must be at least 8 characters")
        return pw
    while True:
        pw = getpass.getpass("Password (min 8 chars): ")
        if len(pw) < 8:
            print("Too short.")
            continue
        if pw != getpass.getpass("Repeat password: "):
            print("Passwords don't match.")
            continue
        return pw


def create_user(email: str, name: str, role: str, alerts: bool) -> None:
    with SessionLocal() as db:
        if db.scalar(select(User).where(func.lower(User.email) == email.lower())):
            sys.exit(f"User {email} already exists. Use set-password to change the password.")
        db.add(
            User(
                email=email.lower(),
                name=name,
                role=Role(role),
                receives_alerts=alerts,
                password_hash=hash_password(_read_password()),
            )
        )
        db.commit()
        print(f"Created {role} {name} <{email}>{' (receives alerts)' if alerts else ''}.")


def set_password(email: str) -> None:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(func.lower(User.email) == email.lower()))
        if not user:
            sys.exit(f"No user {email}")
        user.password_hash = hash_password(_read_password())
        user.sessions.clear()  # log out everywhere
        db.commit()
        print("Password updated; all sessions logged out.")


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("seed")
    p = sub.add_parser("create-user")
    p.add_argument("--email", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--role", choices=["owner", "admin"], required=True)
    p.add_argument("--alerts", action="store_true", help="receive disconnect alert emails")
    p = sub.add_parser("set-password")
    p.add_argument("--email", required=True)
    args = parser.parse_args()

    if args.cmd == "seed":
        seed()
    elif args.cmd == "create-user":
        create_user(args.email, args.name, args.role, args.alerts)
    elif args.cmd == "set-password":
        set_password(args.email)


if __name__ == "__main__":
    main()

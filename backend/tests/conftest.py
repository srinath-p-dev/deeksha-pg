"""Test setup: a separate `<db>_test` database, rebuilt for every test run.

Run from backend/:  pytest -q
"""

import os

from dotenv_shim import load_root_env

load_root_env()
_base_url = os.environ["DATABASE_URL"]
_test_db = _base_url.rsplit("/", 1)[1] + "_test"
os.environ["DATABASE_URL"] = _base_url.rsplit("/", 1)[0] + "/" + _test_db
os.environ["STORAGE_DIR"] = os.path.join(os.path.dirname(__file__), ".storage")
os.environ["WA_MIN_DELAY_SECONDS"] = "0"
os.environ["WA_MAX_DELAY_SECONDS"] = "0"

import psycopg  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402


def _create_test_db():
    admin_url = _base_url.replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(admin_url, autocommit=True) as conn:
        exists = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (_test_db,)).fetchone()
        if not exists:
            conn.execute(f'CREATE DATABASE "{_test_db}"')


_create_test_db()

from app import cli  # noqa: E402
from app.core.db import Base, SessionLocal, engine  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402
from app.models.enums import Role  # noqa: E402
from app.services.app_settings import set_app_setting  # noqa: E402

PASSWORD = "test-password-123"


@pytest.fixture(scope="session", autouse=True)
def schema():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture(autouse=True)
def clean_db(schema):
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    cli.seed()
    with SessionLocal() as db:
        db.add(
            User(
                email="owner@example.com",
                name="Owner",
                role=Role.owner,
                receives_alerts=True,
                password_hash=hash_password(PASSWORD),
            )
        )
        set_app_setting(db, "owner_whatsapp", "919000000000")
        db.commit()
    yield


@pytest.fixture
def anon():
    return TestClient(app)


@pytest.fixture
def client():
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"email": "owner@example.com", "password": PASSWORD})
    assert r.status_code == 200, r.text
    return c


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session

from collections.abc import Iterator

from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

# The engine owns a pool of DB connections, created once for the whole app.
# pool_pre_ping checks a connection is alive before using it (survives DB restarts).
engine = create_engine(settings.database_url, pool_pre_ping=True)

# A factory that produces Session objects bound to the engine.
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

# Predictable constraint names make Alembic migrations stable and readable.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one DB session per request, always closed afterwards.

    Code before `yield` runs before the endpoint; code after runs once the
    response is done, even if the endpoint raised an error.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

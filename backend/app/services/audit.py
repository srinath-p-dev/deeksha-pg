from typing import Any

from sqlalchemy.orm import Session

from app.messaging.outbox import notify_owner
from app.models import AuditLog, User


def record_change(
    db: Session,
    actor: User | None,
    entity_type: str,
    entity_id: int | None,
    action: str,
    summary: str,
    changes: dict[str, Any] | None = None,
    notify: bool = True,
) -> None:
    """Write an audit-log entry and (by default) WhatsApp the owner the same summary.

    Both join the caller's transaction, so nothing is logged or sent unless the
    change itself is committed.
    """
    actor_name = actor.name if actor else "system"
    db.add(
        AuditLog(
            actor_user_id=actor.id if actor else None,
            actor_name=actor_name,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            summary=summary,
            changes=changes or {},
        )
    )
    if notify:
        notify_owner(db, f"{summary}\n— by {actor_name}")

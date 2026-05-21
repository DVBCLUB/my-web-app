"""Small audit helpers for business managers."""

from __future__ import annotations

from functools import wraps
import json

from database import get_connection


def write_audit(action: str, entity_type: str, entity_id=None, old_value=None,
                new_value=None, actor_id=None) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO audit_log (entity_type, entity_id, action, old_value, new_value, actor_id)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        entity_type,
        entity_id,
        action,
        json.dumps(old_value, ensure_ascii=False, default=str) if old_value is not None else None,
        json.dumps(new_value, ensure_ascii=False, default=str) if new_value is not None else None,
        actor_id,
    ))
    conn.commit()


def audited(action: str, entity_type: str | None = None):
    """Decorator ghi audit_log sau khi method business chay thanh cong."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(self, *args, **kwargs):
            result = fn(self, *args, **kwargs)
            actor_id = kwargs.get("created_by") or kwargs.get("approved_by") or kwargs.get("user_id")
            entity_id = result if isinstance(result, int) else kwargs.get("id")
            write_audit(
                action=action,
                entity_type=entity_type or self.__class__.__name__,
                entity_id=entity_id,
                new_value={"args": args, "kwargs": kwargs},
                actor_id=actor_id,
            )
            return result
        return wrapper
    return decorator

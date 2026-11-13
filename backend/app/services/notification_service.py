# Stage notifications in the caller's transaction and mark owned notifications as read.

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models as m
from app.core.errors import missing


def notify(db: Session, user_id: str, message: str, path: str) -> None:
    # Leave the commit to the caller so the update and its notification succeed together.
    db.add(m.Notification(user_id=user_id, message=message, target_path=path))


def mark_read(db: Session, user: m.User, notification_id: str) -> m.Notification:
    record = db.scalar(
        select(m.Notification)
        .where(m.Notification.id == notification_id, m.Notification.user_id == user.id)
        .with_for_update()
    )
    if record is None:
        missing()
    if record.read_at is None:
        record.read_at = m.utcnow()
    db.commit()
    return record

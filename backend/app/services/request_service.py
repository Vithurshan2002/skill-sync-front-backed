# Create and edit customer requests while preserving the details of booked work.

from sqlalchemy.orm import Session

from app import models as m
from app import schemas as s
from app.core.auth import require_role
from app.core.errors import conflict
from app.services.service_queries import category_by_label, request_record
from app.services.workflows import (
    validate_location,
)


def create_request(db: Session, user: m.User, data: s.RequestCreate) -> m.ServiceRequest:
    require_role(user, "customer")
    values = data.model_dump(exclude={"category"})
    validate_location(None, values)
    record = m.ServiceRequest(
        **values, customer_id=user.id, category=category_by_label(db, data.category)
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def patch_request(
    db: Session, user: m.User, record_id: str, data: s.RequestPatch
) -> m.ServiceRequest:
    require_role(user, "customer")
    # Lock against simultaneous booking so agreed request details cannot change mid-booking.
    record = request_record(db, user, record_id, lock=True)
    if record.status != "submitted":
        conflict("Only an unbooked request can be edited.")
    values = data.model_dump(exclude_unset=True)
    validate_location(record, values)
    if "category" in values:
        record.category = category_by_label(db, values.pop("category"))
    for key, value in values.items():
        setattr(record, key, value)
    db.commit()
    db.refresh(record)
    return record

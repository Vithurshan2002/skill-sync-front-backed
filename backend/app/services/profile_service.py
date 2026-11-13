from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models as m
from app import schemas as s
from app.core.auth import own_worker, require_role
from app.core.errors import invalid
from app.services.notification_service import notify
from app.services.service_queries import category_by_label
from app.services.workflows import (
    profile_changes,
    profile_snapshot,
    review_ready,
    validate_location,
)


def patch_customer(db: Session, user: m.User, data: s.ProfilePatch) -> m.User:
    require_role(user, "customer")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(user, key, value)
    db.commit()
    return user


def patch_worker(db: Session, user: m.User, data: s.WorkerPatch) -> m.Worker:
    record = own_worker(db, user, lock=True)
    values = data.model_dump(exclude_unset=True)
    validate_location(record, values, worker=True)
    before = profile_snapshot(record)
    was_ready = review_ready(record)
    if "categories" in values:
        labels = list(dict.fromkeys(values.pop("categories")))
        categories = [category_by_label(db, label) for label in labels]
        existing = {entry.category_id: entry for entry in record.services}
        record.services = [
            existing.get(category.id) or m.WorkerCategory(category=category)
            for category in categories
        ]
    if "service_towns" in values:
        towns = {town.casefold(): town for town in values.pop("service_towns")}
        existing = {entry.town_key: entry for entry in record.towns}
        record.towns = [
            existing.get(key) or m.WorkerTown(town_key=key, town=town)
            for key, town in towns.items()
        ]
    for key, value in values.items():
        setattr(
            user if key in {"name", "town", "phone", "contact_preference"} else record, key, value
        )
    if record.available and (
        not record.services or not record.towns or not record.rate_lkr or len(record.bio) < 15
    ):
        invalid(
            "available",
            "Complete your biography, services, service towns, and rate before becoming available.",
        )
    after = profile_snapshot(record)
    if before != after:
        if record.review_baseline is None:
            record.review_baseline = before
        record.approval_status = "pending"
        record.verified = False
        if any(before[key] != after[key] for key in ["latitude", "longitude", "serviceRadiusKm"]):
            record.location_updated_at = m.utcnow()
    if review_ready(record) and (before != after or not was_ready):
        record.approval_status = "pending"
        fields = ", ".join(change["label"] for change in profile_changes(record))
        for admin_id in db.scalars(select(m.User.id).where(m.User.role == "admin")):
            notify(
                db,
                admin_id,
                f"Review worker profile: {user.name}. Changed: {fields}"[:500],
                f"/admin/records?entity=workers&recordId={record.id}&detailTab=changes",
            )
    db.commit()
    db.refresh(record)
    return record

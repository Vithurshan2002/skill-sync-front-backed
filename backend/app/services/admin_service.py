"""Administrative writes, audit records and notifications in one transaction."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models as m
from app import schemas as s
from app.core.errors import conflict, invalid, missing
from app.schemas import serializers as out
from app.services.notification_service import notify
from app.services.workflows import profile_changes, profile_snapshot, review_ready


def update_category(category_id: str, data: s.CategoryPatch, admin: m.User, db: Session):
    record = db.scalar(select(m.Category).where(m.Category.id == category_id).with_for_update())
    if record is None:
        missing()
    before = out.category(record)
    record.description = data.description
    record.example_request = data.example_request
    db.add(
        m.AuditEvent(
            actor_id=admin.id,
            action="category.updated",
            record_id=record.id,
            details={"before": before, "after": out.category(record)},
        )
    )
    db.commit()
    return {"data": out.category(record)}


def verify_worker(worker_id: str, data: s.VerificationPatch, admin: m.User, db: Session):
    record = db.scalar(select(m.Worker).where(m.Worker.id == worker_id).with_for_update())
    if record is None:
        missing()
    before = record.verified
    if data.verified and not review_ready(record):
        invalid(
            "verified",
            "A complete biography, services, service towns and positive rate "
            "are required for approval.",
        )
    changes = profile_changes(record)
    reviewed_profile = profile_snapshot(record)
    record.verified = data.verified
    record.approval_status = "approved" if data.verified else "changes_requested"
    record.review_note = data.note
    record.reviewed_at = m.utcnow()
    if data.verified:
        record.review_baseline = None
    elif record.review_baseline is None:
        record.review_baseline = reviewed_profile
    db.add(
        m.AuditEvent(
            actor_id=admin.id,
            action="worker.verification",
            record_id=record.id,
            details={
                "before": before,
                "after": data.verified,
                "note": data.note,
                "profileChanges": changes,
                "reviewedProfile": reviewed_profile,
            },
        )
    )
    notify(
        db,
        record.user_id,
        f"Profile {'approved' if data.verified else 'changes requested'}: {data.note}"[:500],
        "/worker/profile",
    )
    db.commit()
    return {"data": out.worker(record, private=True)}


def resolve_complaint(complaint_id: str, data: s.ComplaintResolution, admin: m.User, db: Session):
    record = db.scalar(select(m.Complaint).where(m.Complaint.id == complaint_id).with_for_update())
    if record is None:
        missing()
    if record.status != "pending":
        conflict("This complaint has already received a final decision.")
    record.status = data.status
    record.resolution = data.resolution
    record.resolved_at = m.utcnow()
    record.resolved_by = admin.id
    db.add(
        m.AuditEvent(
            actor_id=admin.id,
            action="complaint.resolved",
            record_id=record.id,
            details={"status": data.status, "resolution": data.resolution},
        )
    )
    booking = db.get(m.Booking, record.booking_id)
    for recipient, path in [
        (booking.customer_id, f"/customer/bookings/{booking.id}"),
        (booking.worker.user_id, f"/worker/jobs/{booking.id}"),
    ]:
        notify(db, recipient, f"Complaint {data.status}: {booking.request.title}", path)
    db.commit()
    return {"data": out.complaint(record)}

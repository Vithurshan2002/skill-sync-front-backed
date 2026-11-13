from typing import Literal

from fastapi import APIRouter
from sqlalchemy import func, select

from app import models as m
from app import schemas as s
from app import serializers as out
from app.auth import Admin, Db
from app.errors import conflict, invalid, missing
from app.routes import PageNumber, PageSize
from app.services import notify, page_result
from app.workflows import profile_changes, profile_snapshot, review_ready

router = APIRouter(prefix="/api/v1/admin", tags=["Administration"])
Entity = Literal[
    "workers", "customers", "categories", "requests", "bookings", "reviews", "complaints"
]
MODELS = {
    "workers": m.Worker,
    "customers": m.User,
    "categories": m.Category,
    "requests": m.ServiceRequest,
    "bookings": m.Booking,
    "reviews": m.Review,
    "complaints": m.Complaint,
}


def entity_query(entity: Entity):
    model = MODELS[entity]
    statement = select(model)
    if entity == "customers":
        statement = statement.where(m.User.role == "customer")
    return statement.order_by(model.id)


def serialize(entity: Entity, db: Db, record):
    serializers = {
        "workers": lambda value: out.worker(value, private=True),
        "categories": out.category,
        "requests": out.service_request,
        "bookings": out.booking,
        "reviews": out.review,
        "customers": lambda value: out.identity(db, value),
        "complaints": out.complaint,
    }
    return serializers[entity](record)


@router.get("/dashboard", response_model=s.Envelope[dict])
def dashboard(admin: Admin, db: Db):
    counts = {
        entity: db.scalar(select(func.count()).select_from(entity_query(entity).subquery()))
        for entity in MODELS
    }
    return {
        "data": {
            "counts": counts,
            "pendingWorkers": sum(
                1
                for worker in db.scalars(
                    select(m.Worker).where(m.Worker.approval_status == "pending")
                )
                if review_ready(worker)
            ),
            "models": {
                "classification": "not_configured",
                "recommendations": "rule_based",
                "performance": "not_configured",
            },
        }
    }


@router.get("/{entity}", response_model=s.Page[dict])
def records(entity: Entity, admin: Admin, db: Db, page: PageNumber = 1, per_page: PageSize = 20):
    return page_result(
        db, entity_query(entity), lambda record: serialize(entity, db, record), page, per_page
    )


@router.get("/{entity}/{record_id}", response_model=s.Envelope[dict])
def details(entity: Entity, record_id: str, admin: Admin, db: Db):
    record = db.scalar(entity_query(entity).where(MODELS[entity].id == record_id))
    if record is None:
        missing()
    return {"data": serialize(entity, db, record)}


@router.patch("/categories/{category_id}", response_model=s.Envelope[s.CategoryView])
def update_category(category_id: str, data: s.CategoryPatch, admin: Admin, db: Db):
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


@router.patch("/workers/{worker_id}/verification", response_model=s.Envelope[s.WorkerView])
def verify_worker(worker_id: str, data: s.VerificationPatch, admin: Admin, db: Db):
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


@router.patch("/complaints/{complaint_id}/resolution", response_model=s.Envelope[dict])
def resolve_complaint(complaint_id: str, data: s.ComplaintResolution, admin: Admin, db: Db):
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

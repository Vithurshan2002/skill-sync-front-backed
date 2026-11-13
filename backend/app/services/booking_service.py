from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models as m
from app import schemas as s
from app.core.auth import require_role
from app.core.errors import ApiError, conflict, invalid, missing
from app.services.notification_service import notify
from app.services.service_queries import booking_record, request_record
from app.services.workflows import (
    covers_location,
)


def ensure_booking_time_available(
    db: Session,
    worker_id: str,
    start: datetime,
    end: datetime | None,
    exclude_id: str | None = None,
) -> None:
    """Caller holds the worker row lock; unknown legacy end times remain open-ended."""
    query = select(m.Booking.id).where(
        m.Booking.worker_id == worker_id,
        m.Booking.status.in_(["pending", "accepted", "in_progress", "awaiting_confirmation"]),
        (func.coalesce(m.Booking.scheduled_end_at, m.Booking.deadline_at) > start)
        | func.coalesce(m.Booking.scheduled_end_at, m.Booking.deadline_at).is_(None),
    )
    if end is not None:
        query = query.where(m.Booking.scheduled_at < end)
    if exclude_id is not None:
        query = query.where(m.Booking.id != exclude_id)
    if db.scalar(query.limit(1)):
        raise ApiError(
            409,
            "booking_time_conflict",
            "This professional already has a booking during that time. Choose another appointment.",
        )


def create_booking(db: Session, user: m.User, data: s.BookingCreate) -> m.Booking:
    require_role(user, "customer")
    request = request_record(db, user, data.request_id, lock=True)
    if request.status != "submitted":
        conflict("This request already has an active or completed booking.")
    if request.category_id is None:
        invalid("requestId", "Select a service category before booking.")
    worker = db.scalar(select(m.Worker).where(m.Worker.id == data.worker_id).with_for_update())
    if worker is None:
        missing()
    if (
        worker.approval_status != "approved"
        or not worker.available
        or worker.rate_lkr is None
        or not any(service.category_id == request.category_id for service in worker.services)
        or not covers_location(worker, request)
    ):
        invalid(
            "workerId",
            "This worker must be approved, available, and offer this service in your location.",
        )
    ensure_booking_time_available(db, worker.id, data.scheduled_at, data.scheduled_end_at)
    record = m.Booking(
        request_id=request.id,
        customer_id=user.id,
        worker_id=worker.id,
        scheduled_at=data.scheduled_at,
        scheduled_end_at=data.scheduled_end_at,
        deadline_at=data.deadline_at,
        quoted_rate_lkr=worker.rate_lkr,
        rate_unit=worker.rate_unit,
    )
    db.add(record)
    db.flush()
    db.add(m.BookingEvent(booking_id=record.id, actor_id=user.id, status="pending"))
    request.status = "booked"
    notify(db, worker.user_id, f"New booking: {request.title}", f"/worker/jobs/{record.id}")
    db.commit()
    db.refresh(record)
    return record


def transition_booking(
    db: Session, user: m.User, record_id: str, data: s.BookingTransition
) -> m.Booking:
    require_role(user, "customer", "worker")
    record = booking_record(db, user, record_id, lock=True)
    allowed = (
        {
            "pending": {"cancelled"},
            "accepted": {"cancelled"},
            "in_progress": {"cancelled"},
            "awaiting_confirmation": {"completed", "in_progress"},
        }
        if user.role == "customer"
        else {
            "pending": {"accepted", "rejected"},
            "accepted": {"in_progress", "cancelled"},
            "in_progress": {"awaiting_confirmation", "cancelled"},
        }
    )
    if data.status not in allowed.get(record.status, set()):
        conflict("This booking transition is not allowed for its current status and your role.")
    if (
        data.status == "cancelled" or (user.role == "customer" and data.status == "in_progress")
    ) and len(data.note or "") < 5:
        invalid("note", "Provide a reason of at least five characters.")
    if data.status in {"accepted", "in_progress"}:
        db.scalar(select(m.Worker).where(m.Worker.id == record.worker_id).with_for_update())
        ensure_booking_time_available(
            db,
            record.worker_id,
            record.scheduled_at,
            record.scheduled_end_at or record.deadline_at,
            record.id,
        )
    now = m.utcnow()
    if data.status == "accepted":
        record.accepted_at = now
    elif data.status == "in_progress":
        record.started_at = record.started_at or now
        record.reported_completed_at = None
    elif data.status == "awaiting_confirmation":
        record.reported_completed_at = now
    elif data.status == "completed":
        record.confirmed_at = now
    elif data.status == "cancelled":
        record.cancelled_at = now
        record.cancelled_by_role = user.role
        record.cancellation_reason = data.note
    record.status = data.status
    db.add(
        m.BookingEvent(booking_id=record.id, actor_id=user.id, status=data.status, note=data.note)
    )
    if data.status in {"rejected", "cancelled"}:
        record.request.status = "submitted"
    elif data.status == "completed":
        record.request.status = "closed"
        db.scalar(select(m.Worker).where(m.Worker.id == record.worker_id).with_for_update())
        metric = db.scalar(
            select(m.WorkerMetric)
            .where(
                m.WorkerMetric.worker_id == record.worker_id,
                m.WorkerMetric.category_id == record.request.category_id,
            )
            .with_for_update(of=m.WorkerMetric)
            .execution_options(populate_existing=True)
        )
        if metric is None:
            metric = m.WorkerMetric(
                worker_id=record.worker_id, category_id=record.request.category_id, completed_jobs=0
            )
            db.add(metric)
        metric.completed_jobs += 1
    recipient = record.worker.user_id if user.role == "customer" else record.customer_id
    path = (
        f"/worker/jobs/{record.id}"
        if user.role == "customer"
        else f"/customer/bookings/{record.id}"
    )
    notify(db, recipient, f"Booking {data.status.replace('_', ' ')}: {record.request.title}", path)
    db.commit()
    db.refresh(record)
    return record


def review_booking(db: Session, user: m.User, record_id: str, data: s.ReviewCreate) -> m.Review:
    require_role(user, "customer")
    booking = booking_record(db, user, record_id, lock=True)
    if booking.status != "completed":
        conflict("You can review only a completed booking.")
    if booking.review is not None:
        conflict("This booking already has a review.")
    worker = db.scalar(
        select(m.Worker)
        .where(m.Worker.id == booking.worker_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    record = m.Review(
        booking_id=booking.id,
        customer_id=user.id,
        worker_id=worker.id,
        rating=data.rating,
        comment=data.comment,
    )
    db.add(record)
    worker.review_count += 1
    worker.rating_total += data.rating
    notify(
        db, worker.user_id, f"New review for: {booking.request.title}", f"/worker/jobs/{booking.id}"
    )
    db.commit()
    db.refresh(record)
    return record


def submit_complaint(
    db: Session, user: m.User, record_id: str, data: s.ComplaintCreate
) -> m.Complaint:
    require_role(user, "customer")
    booking = booking_record(db, user, record_id, lock=True)
    if booking.status not in {"in_progress", "awaiting_confirmation", "completed", "cancelled"}:
        conflict("A complaint can be submitted for started, completed, or cancelled work.")
    if booking.complaint is not None:
        conflict("This booking already has a complaint.")
    record = m.Complaint(booking_id=booking.id, reported_by=user.id, reason=data.reason)
    db.add(record)
    db.flush()
    notify(
        db,
        booking.worker.user_id,
        f"Complaint submitted: {booking.request.title}",
        f"/worker/jobs/{booking.id}",
    )
    for admin_id in db.scalars(select(m.User.id).where(m.User.role == "admin")):
        notify(
            db,
            admin_id,
            f"Complaint requires review: {booking.request.title}",
            f"/admin/records?entity=complaints&recordId={record.id}",
        )
    db.commit()
    db.refresh(record)
    return record

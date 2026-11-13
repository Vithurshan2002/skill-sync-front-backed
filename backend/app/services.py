from collections.abc import Callable
from datetime import datetime
from math import ceil

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models as m
from app import schemas as s
from app import serializers as out
from app.auth import own_worker, require_role
from app.errors import ApiError, conflict, invalid, missing
from app.workflows import (
    covers_location,
    distance_km,
    profile_changes,
    profile_snapshot,
    review_ready,
    validate_location,
)


def category_by_label(db: Session, label: str | None) -> m.Category | None:
    if label is None:
        return None
    record = db.scalar(select(m.Category).where(m.Category.label == label))
    if record is None:
        invalid("category", "Select one of the ten supported service categories.")
    return record


def page_result(db: Session, statement, serializer: Callable, page: int, per_page: int) -> dict:
    total = db.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
    records = db.scalars(statement.offset((page - 1) * per_page).limit(per_page)).all()
    return {
        "data": [serializer(record) for record in records],
        "meta": {
            "page": page,
            "perPage": per_page,
            "total": total,
            "lastPage": max(1, ceil(total / per_page)),
        },
    }


def worker_query(
    category: str | None = None,
    town: str | None = None,
    available: bool | None = None,
    max_rate=None,
    search: str | None = None,
):
    statement = (
        select(m.Worker)
        .join(m.User, m.User.id == m.Worker.user_id)
        .where(
            m.Worker.approval_status == "approved",
            m.Worker.rate_lkr.is_not(None),
            m.Worker.services.any(),
            m.Worker.towns.any(),
        )
    )
    if category:
        statement = statement.where(
            m.Worker.services.any(m.WorkerCategory.category.has(m.Category.label == category))
        )
    if town:
        statement = statement.where(
            m.Worker.towns.any(m.WorkerTown.town_key == town.strip().casefold())
        )
    if available is not None:
        statement = statement.where(m.Worker.available == available)
    if max_rate is not None:
        statement = statement.where(m.Worker.rate_lkr <= max_rate)
    if search:
        needle = search.strip().casefold()
        statement = statement.where(
            func.lower(m.User.name).contains(needle, autoescape=True)
            | m.Worker.services.any(
                m.WorkerCategory.category.has(
                    func.lower(m.Category.label).contains(needle, autoescape=True)
                )
            )
        )
    return statement.order_by(func.lower(m.User.name), m.Worker.id)


def request_record(
    db: Session, user: m.User, record_id: str, lock: bool = False
) -> m.ServiceRequest:
    require_role(user, "customer", "admin")
    statement = select(m.ServiceRequest).where(m.ServiceRequest.id == record_id)
    if user.role == "customer":
        statement = statement.where(m.ServiceRequest.customer_id == user.id)
    if lock:
        statement = statement.with_for_update()
    record = db.scalar(statement)
    if record is None:
        missing()
    return record


def booking_query(user: m.User, db: Session):
    statement = select(m.Booking)
    if user.role == "customer":
        statement = statement.where(m.Booking.customer_id == user.id)
    elif user.role == "worker":
        worker = own_worker(db, user)
        statement = statement.where(m.Booking.worker_id == worker.id)
    return statement


def booking_record(db: Session, user: m.User, record_id: str, lock: bool = False) -> m.Booking:
    statement = booking_query(user, db).where(m.Booking.id == record_id)
    record = db.scalar(statement)
    if record is None:
        missing()
    if lock:
        # Every booking write locks the request first, then booking, then worker.
        db.scalar(
            select(m.ServiceRequest)
            .where(m.ServiceRequest.id == record.request_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        record = db.scalar(statement.with_for_update().execution_options(populate_existing=True))
    return record


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


def notify(db: Session, user_id: str, message: str, path: str) -> None:
    db.add(m.Notification(user_id=user_id, message=message, target_path=path))


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


def recommendations(
    db: Session, user: m.User, record_id: str, filters: s.RecommendationFilters
) -> dict:
    require_role(user, "customer")
    request = request_record(db, user, record_id)
    if request.status != "submitted":
        conflict("Recommendations are available only for an unbooked request.")
    if request.category is None:
        invalid(
            "category", "Select a service category manually; no classification model is installed."
        )
    statement = worker_query(request.category.label, None, filters.available, filters.max_rate)
    workers = [worker for worker in db.scalars(statement) if covers_location(worker, request)][:50]
    return {
        "requestId": request.id,
        "category": request.category.label,
        "source": "rule_based",
        "recommendations": [
            {
                "workerId": worker.id,
                "rank": rank,
                "source": "rule_based",
                "matchScore": None,
                "categorySkillScore": None,
                "reliabilityProbability": None,
                "distanceKm": round(distance_km(worker, request), 2)
                if distance_km(worker, request) is not None
                else None,
                "reasons": [
                    f"Offers {request.category.label}",
                    f"Within {worker.service_radius_km} km service radius"
                    if distance_km(worker, request) is not None
                    else f"Serves {request.town}",
                    "Available for new jobs" if worker.available else "Currently unavailable",
                    "Alphabetical order among eligible workers; not an AI ranking",
                ],
                "worker": out.worker(worker),
            }
            for rank, worker in enumerate(workers, start=1)
        ],
    }


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


def unavailable_classifier() -> None:
    raise ApiError(
        503,
        "model_unavailable",
        "No trained classification model is installed. Select a service category manually.",
    )

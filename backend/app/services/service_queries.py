# Shared filtered queries, ownership-scoped lookups, and pagination metadata.

from collections.abc import Callable
from math import ceil

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models as m
from app.core.auth import own_worker, require_role
from app.core.errors import invalid, missing


def category_by_label(db: Session, label: str | None) -> m.Category | None:
    if label is None:
        return None
    record = db.scalar(select(m.Category).where(m.Category.label == label))
    if record is None:
        invalid("category", "Select one of the ten supported service categories.")
    return record


def page_result(db: Session, statement, serializer: Callable, page: int, per_page: int) -> dict:
    # The caller has already applied filters and ownership rules; count that same result set.
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

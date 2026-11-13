from typing import Literal

from fastapi import APIRouter, Query
from sqlalchemy import String, cast, func, or_, select

from app import models as m
from app import schemas as s
from app.api.dependencies import PageNumber, PageSize
from app.core.auth import Admin, Db
from app.core.errors import missing
from app.schemas import serializers as out
from app.services import admin_service
from app.services.service_queries import page_result
from app.services.workflows import review_ready

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


def entity_query(entity: Entity, search: str | None = None, pending_only: bool = False):
    model = MODELS[entity]
    statement = select(model)
    if entity == "customers":
        statement = statement.where(m.User.role == "customer")
    if pending_only and entity == "workers":
        statement = statement.where(
            m.Worker.approval_status == "pending",
            m.Worker.services.any(),
            m.Worker.towns.any(),
            m.Worker.rate_lkr > 0,
            func.length(m.Worker.bio) >= 15,
        )
    if search and search.strip():
        needle = search.strip().lower()
        fields = [
            column
            for column in model.__table__.columns
            if isinstance(column.type, String) and column.name not in {"password_hash", "photo_key"}
        ]
        predicates = [
            func.lower(cast(column, String)).contains(needle, autoescape=True) for column in fields
        ]
        if entity == "workers":
            predicates.append(
                m.Worker.user.has(
                    or_(
                        func.lower(m.User.name).contains(needle, autoescape=True),
                        func.lower(m.User.town).contains(needle, autoescape=True),
                    )
                )
            )
        statement = statement.where(or_(*predicates))
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
def records(
    entity: Entity,
    admin: Admin,
    db: Db,
    page: PageNumber = 1,
    per_page: PageSize = 20,
    search: str | None = Query(default=None, max_length=200),
    pending_only: bool = Query(default=False, alias="pendingOnly"),
):
    return page_result(
        db,
        entity_query(entity, search, pending_only),
        lambda record: serialize(entity, db, record),
        page,
        per_page,
    )


@router.get("/{entity}/{record_id}", response_model=s.Envelope[dict])
def details(entity: Entity, record_id: str, admin: Admin, db: Db):
    record = db.scalar(entity_query(entity).where(MODELS[entity].id == record_id))
    if record is None:
        missing()
    return {"data": serialize(entity, db, record)}


@router.patch("/categories/{category_id}", response_model=s.Envelope[s.CategoryView])
def update_category(category_id: str, data: s.CategoryPatch, admin: Admin, db: Db):
    return admin_service.update_category(category_id, data, admin, db)


@router.patch("/workers/{worker_id}/verification", response_model=s.Envelope[s.WorkerView])
def verify_worker(worker_id: str, data: s.VerificationPatch, admin: Admin, db: Db):
    return admin_service.verify_worker(worker_id, data, admin, db)


@router.patch("/complaints/{complaint_id}/resolution", response_model=s.Envelope[dict])
def resolve_complaint(complaint_id: str, data: s.ComplaintResolution, admin: Admin, db: Db):
    return admin_service.resolve_complaint(complaint_id, data, admin, db)

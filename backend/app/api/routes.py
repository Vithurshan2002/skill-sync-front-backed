# HTTP boundary for customer and worker features; services handle business mutations.

from typing import Annotated, Literal

from fastapi import APIRouter, Query, Request
from sqlalchemy import func, select

from app import models as m
from app import schemas as s
from app.api.dependencies import PageNumber, PageSize
from app.core.auth import (
    CurrentUser,
    Db,
    own_worker,
    require_role,
)
from app.core.errors import missing
from app.schemas import serializers as out
from app.services import (
    account_service,
    booking_service,
    matching_service,
    notification_service,
    profile_service,
    request_service,
    service_queries,
)

router = APIRouter(prefix="/api/v1")


@router.post(
    "/auth/register",
    response_model=s.Envelope[s.TokenResult],
    status_code=201,
    tags=["Authentication"],
)
def register(data: s.Register, db: Db, request: Request):
    return {
        "data": account_service.register_account(
            db, data, request.app.state.settings.token_ttl_minutes
        )
    }


@router.post("/auth/login", response_model=s.Envelope[s.TokenResult], tags=["Authentication"])
def login(data: s.Login, db: Db, request: Request):
    return {
        "data": account_service.login_account(
            db, data, request.app.state.settings.token_ttl_minutes
        )
    }


@router.post("/auth/logout", response_model=s.Envelope[dict], tags=["Authentication"])
def logout(request: Request, user: CurrentUser, db: Db):
    account_service.revoke_token(db, request.state.token_digest)
    return {"data": {"message": "Signed out. This access token has been revoked."}}


@router.get("/me", response_model=s.Envelope[s.Identity], tags=["Profiles"])
def me(user: CurrentUser, db: Db):
    return {"data": out.identity(db, user)}


@router.patch("/me", response_model=s.Envelope[s.Identity], tags=["Profiles"])
def update_me(data: s.ProfilePatch, user: CurrentUser, db: Db):
    return {"data": out.identity(db, profile_service.patch_customer(db, user, data))}


@router.get("/categories", response_model=s.Envelope[list[s.CategoryView]], tags=["Categories"])
def categories(db: Db):
    return {
        "data": [
            out.category(record)
            for record in db.scalars(select(m.Category).order_by(m.Category.label))
        ]
    }


@router.get("/workers", response_model=s.Page[s.WorkerView], tags=["Workers"])
def workers(
    db: Db,
    page: PageNumber = 1,
    per_page: PageSize = 12,
    search: Annotated[str | None, Query(max_length=100)] = None,
    category: Annotated[str | None, Query(max_length=80)] = None,
    town: Annotated[str | None, Query(max_length=100)] = None,
    available: bool | None = None,
    max_rate: Annotated[float | None, Query(gt=0, le=9999999999, alias="maxRate")] = None,
):
    if category:
        service_queries.category_by_label(db, category)
    query = service_queries.worker_query(category, town, available, max_rate, search)
    return service_queries.page_result(db, query, out.worker, page, per_page)


@router.get("/workers/{worker_id}", response_model=s.Envelope[s.WorkerDetail], tags=["Workers"])
def worker_details(worker_id: str, db: Db):
    record = db.get(m.Worker, worker_id)
    if record is None or record.approval_status != "approved":
        missing()
    reviews = db.scalars(
        select(m.Review)
        .where(m.Review.worker_id == worker_id)
        .order_by(m.Review.created_at.desc(), m.Review.id)
        .limit(20)
    ).all()
    return {
        "data": {
            **out.worker(record),
            "reviews": [
                {
                    "rating": review.rating,
                    "comment": review.comment,
                    "createdAt": out.aware(review.created_at),
                    "customerName": (review.customer.name.split() or ["Customer"])[0],
                }
                for review in reviews
            ],
        }
    }


@router.get("/worker/profile", response_model=s.Envelope[s.WorkerView], tags=["Profiles"])
def worker_profile(user: CurrentUser, db: Db):
    return {"data": out.worker(own_worker(db, user), private=True)}


@router.patch("/worker/profile", response_model=s.Envelope[s.WorkerView], tags=["Profiles"])
def update_worker_profile(data: s.WorkerPatch, user: CurrentUser, db: Db):
    return {"data": out.worker(profile_service.patch_worker(db, user, data), private=True)}


@router.get("/worker/performance", response_model=s.Envelope[dict], tags=["Workers"])
def worker_performance(user: CurrentUser, db: Db):
    record = own_worker(db, user)
    profile = out.worker(record)
    return {
        "data": {
            "workerId": record.id,
            "performance": profile["performance"],
            "completedJobs": sum(metric.completed_jobs for metric in record.metrics),
            "rating": profile["rating"],
            "reviewCount": profile["reviewCount"],
            "reliabilityProbability": None,
            "modelStatus": "not_configured",
            "source": "booking_history",
            "modelVersion": None,
        }
    }


@router.get("/requests", response_model=s.Page[s.RequestView], tags=["Requests"])
def requests(user: CurrentUser, db: Db, page: PageNumber = 1, per_page: PageSize = 20):
    require_role(user, "customer", "admin")
    query = select(m.ServiceRequest)
    if user.role == "customer":
        query = query.where(m.ServiceRequest.customer_id == user.id)
    return service_queries.page_result(
        db,
        query.order_by(m.ServiceRequest.created_at.desc(), m.ServiceRequest.id),
        out.service_request,
        page,
        per_page,
    )


@router.post(
    "/requests", response_model=s.Envelope[s.RequestView], status_code=201, tags=["Requests"]
)
def create_request(data: s.RequestCreate, user: CurrentUser, db: Db):
    return {"data": out.service_request(request_service.create_request(db, user, data))}


@router.get("/requests/{request_id}", response_model=s.Envelope[s.RequestView], tags=["Requests"])
def request_details(request_id: str, user: CurrentUser, db: Db):
    return {"data": out.service_request(service_queries.request_record(db, user, request_id))}


@router.patch("/requests/{request_id}", response_model=s.Envelope[s.RequestView], tags=["Requests"])
def update_request(request_id: str, data: s.RequestPatch, user: CurrentUser, db: Db):
    return {"data": out.service_request(request_service.patch_request(db, user, request_id, data))}


@router.post("/requests/{request_id}/classify", response_model=s.Envelope[dict], tags=["Matching"])
def classify(request_id: str, user: CurrentUser, db: Db):
    require_role(user, "customer")
    service_queries.request_record(db, user, request_id)
    matching_service.unavailable_classifier()


@router.post(
    "/requests/{request_id}/recommendations",
    response_model=s.Envelope[s.RecommendationResult],
    tags=["Matching"],
)
def recommendations(request_id: str, data: s.RecommendationFilters, user: CurrentUser, db: Db):
    return {"data": matching_service.recommendations(db, user, request_id, data)}


@router.get("/bookings", response_model=s.Page[s.BookingView], tags=["Bookings"])
def bookings(
    user: CurrentUser,
    db: Db,
    page: PageNumber = 1,
    per_page: PageSize = 20,
    status: Literal[
        "pending",
        "accepted",
        "in_progress",
        "awaiting_confirmation",
        "completed",
        "rejected",
        "cancelled",
    ]
    | None = None,
    search: str | None = Query(default=None, max_length=200),
    group: Literal["active", "confirmed"] | None = None,
    order: Literal["scheduled_desc", "scheduled_asc"] = "scheduled_desc",
):
    query = service_queries.booking_query(user, db).order_by(
        m.Booking.scheduled_at.asc() if order == "scheduled_asc" else m.Booking.scheduled_at.desc(),
        m.Booking.id,
    )
    # Dashboard groups reuse the ownership-scoped query before pagination is applied.
    if group:
        statuses = ["accepted", "in_progress", "awaiting_confirmation"]
        if group == "active":
            statuses.append("pending")
        query = query.where(m.Booking.status.in_(statuses))
    if status:
        query = query.where(m.Booking.status == status)
    if search and search.strip():
        needle = search.strip().lower()
        query = query.where(
            m.Booking.request.has(
                func.lower(m.ServiceRequest.title).contains(needle, autoescape=True)
                | func.lower(m.ServiceRequest.town).contains(needle, autoescape=True)
            )
        )
    return service_queries.page_result(db, query, out.booking, page, per_page)


@router.post(
    "/bookings", response_model=s.Envelope[s.BookingView], status_code=201, tags=["Bookings"]
)
def create_booking(data: s.BookingCreate, user: CurrentUser, db: Db):
    return {"data": out.booking(booking_service.create_booking(db, user, data))}


@router.get("/bookings/{booking_id}", response_model=s.Envelope[s.BookingView], tags=["Bookings"])
def booking_details(booking_id: str, user: CurrentUser, db: Db):
    return {"data": out.booking(service_queries.booking_record(db, user, booking_id))}


@router.patch(
    "/bookings/{booking_id}/status", response_model=s.Envelope[s.BookingView], tags=["Bookings"]
)
def booking_status(booking_id: str, data: s.BookingTransition, user: CurrentUser, db: Db):
    return {"data": out.booking(booking_service.transition_booking(db, user, booking_id, data))}


@router.post(
    "/bookings/{booking_id}/review",
    response_model=s.Envelope[s.ReviewView],
    status_code=201,
    tags=["Reviews"],
)
def create_review(booking_id: str, data: s.ReviewCreate, user: CurrentUser, db: Db):
    return {"data": out.review(booking_service.review_booking(db, user, booking_id, data))}


@router.post(
    "/bookings/{booking_id}/complaint",
    response_model=s.Envelope[dict],
    status_code=201,
    tags=["Complaints"],
)
def create_complaint(booking_id: str, data: s.ComplaintCreate, user: CurrentUser, db: Db):
    return {"data": out.complaint(booking_service.submit_complaint(db, user, booking_id, data))}


@router.get("/notifications", response_model=s.Page[s.NotificationView], tags=["Notifications"])
def notifications(
    user: CurrentUser, db: Db, page: PageNumber = 1, per_page: PageSize = 20, unread: bool = False
):
    query = select(m.Notification).where(m.Notification.user_id == user.id)
    if unread:
        query = query.where(m.Notification.read_at.is_(None))
    return service_queries.page_result(
        db,
        query.order_by(m.Notification.created_at.desc(), m.Notification.id),
        out.notification,
        page,
        per_page,
    )


@router.patch(
    "/notifications/{notification_id}",
    response_model=s.Envelope[s.NotificationView],
    tags=["Notifications"],
)
def read_notification(notification_id: str, data: s.NotificationRead, user: CurrentUser, db: Db):
    return {"data": out.notification(notification_service.mark_read(db, user, notification_id))}


@router.get("/dashboard", response_model=s.Envelope[dict], tags=["Dashboard"])
def dashboard(user: CurrentUser, db: Db):
    query = service_queries.booking_query(user, db).with_only_columns(
        m.Booking.status, func.count()
    )
    counts = dict(db.execute(query.group_by(m.Booking.status)).all())
    request_query = select(func.count()).select_from(m.ServiceRequest)
    if user.role == "customer":
        request_query = request_query.where(m.ServiceRequest.customer_id == user.id)
    return {
        "data": {
            "role": user.role,
            "bookingsByStatus": counts,
            "bookings": sum(counts.values()),
            "requests": db.scalar(request_query) if user.role != "worker" else None,
            "unreadNotifications": db.scalar(
                select(func.count())
                .select_from(m.Notification)
                .where(m.Notification.user_id == user.id, m.Notification.read_at.is_(None))
            ),
        }
    }

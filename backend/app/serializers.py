from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models as m
from app.workflows import profile_changes, review_ready


def aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def identity(db: Session, user: m.User) -> dict:
    worker_id = db.scalar(select(m.Worker.id).where(m.Worker.user_id == user.id))
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "workerId": worker_id,
        "town": user.town,
        "phone": user.phone,
        "contactPreference": user.contact_preference,
    }


def category(value: m.Category) -> dict:
    return {
        "id": value.id,
        "label": value.label,
        "slug": value.slug,
        "icon": value.icon,
        "description": value.description,
        "exampleRequest": value.example_request,
    }


def worker(value: m.Worker, private: bool = False) -> dict:
    metrics = {metric.category.label: metric.completed_jobs for metric in value.metrics}
    labels = sorted(service.category.label for service in value.services)
    return {
        "photoUrl": f"/api/v1/worker-photos/{value.photo_key}.jpg" if value.photo_key else None,
        "latitude": float(value.latitude) if private and value.latitude is not None else None,
        "longitude": float(value.longitude) if private and value.longitude is not None else None,
        "serviceRadiusKm": float(value.service_radius_km)
        if value.service_radius_km is not None
        else None,
        "locationUpdatedAt": aware(value.location_updated_at),
        "approvalStatus": value.approval_status,
        "reviewReady": review_ready(value),
        "reviewNote": value.review_note if private else None,
        "reviewedAt": aware(value.reviewed_at) if private else None,
        "profileChanges": profile_changes(value) if private else [],
        "id": value.id,
        "name": value.user.name,
        "town": value.user.town,
        "serviceTowns": sorted(town.town for town in value.towns),
        "categories": labels,
        "bio": value.bio,
        "yearsExperience": value.years_experience,
        "rateLkr": float(value.rate_lkr) if value.rate_lkr is not None else None,
        "rateUnit": value.rate_unit,
        "available": value.available,
        "rating": round(value.rating_total / value.review_count, 2) if value.review_count else None,
        "reviewCount": value.review_count,
        "reliabilityProbability": None,
        "verified": value.verified,
        "performance": [
            {"category": label, "skillScore": None, "completedJobs": metrics.get(label, 0)}
            for label in sorted(set(labels) | metrics.keys())
        ],
    }


def service_request(value: m.ServiceRequest) -> dict:
    return {
        "latitude": float(value.latitude) if value.latitude is not None else None,
        "longitude": float(value.longitude) if value.longitude is not None else None,
        "id": value.id,
        "customerId": value.customer_id,
        "title": value.title,
        "description": value.description,
        "town": value.town,
        "address": value.address,
        "preferredAt": aware(value.preferred_at),
        "budgetLkr": float(value.budget_lkr) if value.budget_lkr is not None else None,
        "category": value.category.label if value.category else None,
        "status": value.status,
        "createdAt": aware(value.created_at),
    }


def review(value: m.Review) -> dict:
    return {
        "id": value.id,
        "bookingId": value.booking_id,
        "customerId": value.customer_id,
        "customerName": (value.customer.name.split() or ["Customer"])[0],
        "workerId": value.worker_id,
        "rating": value.rating,
        "comment": value.comment,
        "createdAt": aware(value.created_at),
    }


def booking(value: m.Booking) -> dict:
    return {
        "scheduledEndAt": aware(value.scheduled_end_at),
        "deadlineAt": aware(value.deadline_at),
        "acceptedAt": aware(value.accepted_at),
        "startedAt": aware(value.started_at),
        "reportedCompletedAt": aware(value.reported_completed_at),
        "confirmedAt": aware(value.confirmed_at),
        "cancelledAt": aware(value.cancelled_at),
        "cancelledByRole": value.cancelled_by_role,
        "cancellationReason": value.cancellation_reason,
        "complaint": complaint(value.complaint) if value.complaint else None,
        "id": value.id,
        "requestId": value.request_id,
        "customerId": value.customer_id,
        "workerId": value.worker_id,
        "scheduledAt": aware(value.scheduled_at),
        "status": value.status,
        "quotedRateLkr": float(value.quoted_rate_lkr),
        "rateUnit": value.rate_unit,
        "history": [
            {"status": event.status, "at": aware(event.at), "note": event.note}
            for event in value.history
        ],
        "request": service_request(value.request),
        "worker": worker(value.worker),
        "review": review(value.review) if value.review else None,
    }


def complaint(value: m.Complaint) -> dict:
    return {
        "id": value.id,
        "bookingId": value.booking_id,
        "reportedBy": value.reported_by,
        "reason": value.reason,
        "status": value.status,
        "resolution": value.resolution,
        "createdAt": aware(value.created_at),
        "resolvedAt": aware(value.resolved_at),
    }


def notification(value: m.Notification) -> dict:
    return {
        "id": value.id,
        "userId": value.user_id,
        "message": value.message,
        "targetPath": value.target_path,
        "createdAt": aware(value.created_at),
        "readAt": aware(value.read_at),
    }

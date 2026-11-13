# Filter eligible workers using service, price, availability, and location rules.

from sqlalchemy.orm import Session

from app import models as m
from app import schemas as s
from app.core.auth import require_role
from app.core.errors import ApiError, conflict, invalid
from app.schemas import serializers as out
from app.services.service_queries import request_record, worker_query
from app.services.workflows import (
    covers_location,
    distance_km,
)


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
    # Apply service coverage before limiting results; ordering is alphabetical, not a score.
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


def unavailable_classifier() -> None:
    raise ApiError(
        503,
        "model_unavailable",
        "No trained classification model is installed. Select a service category manually.",
    )

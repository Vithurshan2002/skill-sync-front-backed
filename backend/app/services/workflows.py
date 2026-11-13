"""Shared eligibility, profile review and geographic rules."""

from math import asin, cos, radians, sin, sqrt

from app import models as m
from app.core.errors import invalid

REVIEW_FIELDS = {
    "name": "Name",
    "town": "Home town",
    "bio": "Biography",
    "categories": "Service categories",
    "serviceTowns": "Service towns",
    "yearsExperience": "Experience",
    "latitude": "Latitude",
    "longitude": "Longitude",
    "serviceRadiusKm": "Service radius",
}


def profile_snapshot(worker: m.Worker) -> dict:
    return {
        "name": worker.user.name,
        "town": worker.user.town,
        "bio": worker.bio,
        "categories": sorted(service.category.label for service in worker.services),
        "serviceTowns": sorted(town.town for town in worker.towns),
        "yearsExperience": worker.years_experience,
        "latitude": float(worker.latitude) if worker.latitude is not None else None,
        "longitude": float(worker.longitude) if worker.longitude is not None else None,
        "serviceRadiusKm": float(worker.service_radius_km)
        if worker.service_radius_km is not None
        else None,
    }


def profile_changes(worker: m.Worker) -> list[dict]:
    current = profile_snapshot(worker)
    baseline = worker.review_baseline
    if baseline is None:
        return []
    return [
        {"field": key, "label": label, "before": baseline.get(key), "after": current[key]}
        for key, label in REVIEW_FIELDS.items()
        if baseline.get(key) != current[key]
    ]


def review_ready(worker: m.Worker) -> bool:
    return bool(worker.services and worker.towns and worker.rate_lkr and len(worker.bio) >= 15)


def validate_location(record, values: dict, worker: bool = False) -> None:
    names = ["latitude", "longitude"] + (["service_radius_km"] if worker else [])
    # Merge PATCH values with saved coordinates before checking that the set is complete.
    coordinates = [values.get(name, getattr(record, name, None)) for name in names]
    if any(value is not None for value in coordinates) and any(
        value is None for value in coordinates
    ):
        invalid(
            "latitude",
            "Provide both coordinates"
            + (" and a service radius, or clear all three." if worker else ", or clear both."),
        )


def distance_km(worker: m.Worker, request: m.ServiceRequest) -> float | None:
    if any(
        value is None
        for value in [worker.latitude, worker.longitude, request.latitude, request.longitude]
    ):
        return None
    lat1, lon1, lat2, lon2 = map(
        lambda value: radians(float(value)),
        [worker.latitude, worker.longitude, request.latitude, request.longitude],
    )
    a = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    # Haversine distance in kilometres; clamp rounding drift before asin().
    return 6371.0088 * 2 * asin(sqrt(min(1, max(0, a))))


def covers_location(worker: m.Worker, request: m.ServiceRequest) -> bool:
    distance = distance_km(worker, request)
    if distance is not None and worker.service_radius_km is not None:
        return distance <= float(worker.service_radius_km)
    # Older profiles without complete coordinates still match by their declared service towns.
    return any(town.town_key == request.town.casefold() for town in worker.towns)

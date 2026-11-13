from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.auth import password_hash
from app.models import User, Worker

PASSWORD = "Test-password-for-SkillSync!"


def account(api, role="customer", name="Anu Test"):
    email = f"{uuid4().hex}@example.com"
    if role == "admin":
        with api.app.state.sessions() as db:
            db.add(
                User(
                    name=name,
                    email=email,
                    password_hash=password_hash.hash(PASSWORD),
                    role="admin",
                    town="Colombo",
                )
            )
            db.commit()
        response = api.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    else:
        response = api.post(
            "/api/v1/auth/register",
            json={
                "name": name,
                "email": email,
                "password": PASSWORD,
                "role": role,
                "town": "Colombo",
            },
        )
    assert response.status_code in {200, 201}, response.text
    data = response.json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}, data["user"]


def worker(api, name="Arul Test", approved=True, **overrides):
    headers, user = account(api, "worker", name)
    payload = {
        "bio": "Careful repairs for household taps and pipes.",
        "categories": ["Plumbing"],
        "serviceTowns": ["Colombo"],
        "yearsExperience": 5,
        "rateLkr": 2500,
        "rateUnit": "visit",
        "available": True,
    }
    payload.update(overrides)
    response = api.patch("/api/v1/worker/profile", headers=headers, json=payload)
    assert response.status_code == 200, response.text
    if approved:
        with api.app.state.sessions() as db:
            record = db.get(Worker, user["workerId"])
            record.approval_status = "approved"
            record.verified = True
            record.review_baseline = None
            db.commit()
    return headers, api.get("/api/v1/worker/profile", headers=headers).json()["data"], user


def request_payload(**overrides):
    data = {
        "title": "Repair a leaking kitchen tap",
        "description": "My kitchen tap keeps leaking even when it is closed.",
        "town": "Colombo",
        "preferredAt": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
        "category": "Plumbing",
        "budgetLkr": 3500,
    }
    data.update(overrides)
    return data


def service_request(api, headers, **overrides):
    response = api.post("/api/v1/requests", headers=headers, json=request_payload(**overrides))
    assert response.status_code == 201, response.text
    return response.json()["data"]


def booking(api, headers, request, worker):
    response = api.post(
        "/api/v1/bookings",
        headers=headers,
        json={
            "requestId": request["id"],
            "workerId": worker["id"],
            "scheduledAt": request["preferredAt"],
            "scheduledEndAt": (
                datetime.fromisoformat(request["preferredAt"]) + timedelta(hours=2)
            ).isoformat(),
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def transition(api, headers, booking_id, status, note=None):
    return api.patch(
        f"/api/v1/bookings/{booking_id}/status",
        headers=headers,
        json={"status": status, "note": note},
    )


def complete(api, headers, booking_id, customer):
    for status in ["accepted", "in_progress", "awaiting_confirmation"]:
        response = transition(api, headers, booking_id, status)
        assert response.status_code == 200, response.text
        assert response.json()["data"]["status"] == status
    response = transition(api, customer, booking_id, "completed")
    assert response.status_code == 200, response.text

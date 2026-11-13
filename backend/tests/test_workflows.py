# Verify approval, service coverage, scheduling, confirmation, and complaint workflows.

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.models import AuditEvent
from tests.helpers import account, booking, service_request, transition, worker


def approve(api, admin, worker_id, verified=True):
    return api.patch(
        f"/api/v1/admin/workers/{worker_id}/verification",
        headers=admin,
        json={"verified": verified, "note": "Checked profile details for this test."},
    )


def test_approval_controls_discovery_and_changes_require_fresh_review(api):
    admin, _ = account(api, "admin")
    headers, profile, _ = worker(api, approved=False)
    worker_id = profile["id"]
    assert profile["approvalStatus"] == "pending"
    assert profile["reviewReady"] is True
    assert api.get("/api/v1/workers").json()["meta"]["total"] == 0
    assert api.get(f"/api/v1/workers/{worker_id}").status_code == 404
    assert approve(api, headers, worker_id).status_code == 403
    assert approve(api, admin, worker_id).status_code == 200
    assert api.get("/api/v1/workers").json()["meta"]["total"] == 1
    assert api.get(f"/api/v1/workers/{worker_id}").json()["data"]["reviewNote"] is None
    # Price/contact updates are routine; service/identity updates need another review.
    assert (
        api.patch("/api/v1/worker/profile", headers=headers, json={"rateLkr": 3000}).json()["data"][
            "approvalStatus"
        ]
        == "approved"
    )
    customer, _ = account(api)
    existing = booking(api, customer, service_request(api, customer), profile)
    changed = api.patch(
        "/api/v1/worker/profile", headers=headers, json={"yearsExperience": 6}
    ).json()["data"]
    assert changed["approvalStatus"] == "pending"
    assert changed["profileChanges"] == [
        {"field": "yearsExperience", "label": "Experience", "before": 5, "after": 6}
    ]
    assert api.get(f"/api/v1/bookings/{existing['id']}", headers=customer).status_code == 200
    assert (
        api.get(f"/api/v1/bookings/{existing['id']}", headers=customer).json()["data"]["worker"][
            "profileChanges"
        ]
        == []
    )
    count = api.get("/api/v1/notifications", headers=admin).json()["meta"]["total"]
    api.patch("/api/v1/worker/profile", headers=headers, json={"yearsExperience": 6})
    assert api.get("/api/v1/notifications", headers=admin).json()["meta"]["total"] == count
    assert (
        approve(api, admin, worker_id, False).json()["data"]["approvalStatus"]
        == "changes_requested"
    )
    changed = api.patch(
        "/api/v1/worker/profile", headers=headers, json={"yearsExperience": 7}
    ).json()["data"]
    assert changed["profileChanges"][0]["before"] == 5
    assert changed["approvalStatus"] == "pending"
    assert approve(api, admin, worker_id).json()["data"]["profileChanges"] == []
    with api.app.state.sessions() as db:
        events = db.scalars(
            select(AuditEvent).where(AuditEvent.action == "worker.verification")
        ).all()
        assert len(events) == 3
        assert any(event.details["profileChanges"] for event in events)


def test_incomplete_profile_cannot_be_approved_and_pending_worker_cannot_be_booked(api):
    admin, _ = account(api, "admin")
    _, identity = account(api, "worker")
    assert approve(api, admin, identity["workerId"]).status_code == 422
    _, profile, _ = worker(api, approved=False)
    customer, _ = account(api)
    req = service_request(api, customer)
    payload = {
        "requestId": req["id"],
        "workerId": profile["id"],
        "scheduledAt": req["preferredAt"],
        "scheduledEndAt": (
            datetime.fromisoformat(req["preferredAt"]) + timedelta(hours=2)
        ).isoformat(),
    }
    assert api.post("/api/v1/bookings", headers=customer, json=payload).status_code == 422


def test_gps_radius_matching_private_coordinates_and_town_fallback(api):
    headers, professional, _ = worker(api, latitude=6.9271, longitude=79.8612, serviceRadiusKm=10)
    customer, _ = account(api)
    nearby = service_request(api, customer, town="Different town", latitude=6.93, longitude=79.86)
    result = api.post(
        f"/api/v1/requests/{nearby['id']}/recommendations", headers=customer, json={}
    ).json()["data"]
    assert result["recommendations"][0]["distanceKm"] < 1
    assert result["recommendations"][0]["worker"]["latitude"] is None
    public = api.get(f"/api/v1/workers/{professional['id']}").json()["data"]
    assert public["latitude"] is None and public["longitude"] is None
    assert api.get("/api/v1/worker/profile", headers=headers).json()["data"]["latitude"] == 6.9271
    distant = service_request(api, customer, latitude=9.6615, longitude=80.0255)
    assert (
        api.post(
            f"/api/v1/requests/{distant['id']}/recommendations", headers=customer, json={}
        ).json()["data"]["recommendations"]
        == []
    )
    no_gps = service_request(api, customer)
    assert (
        len(
            api.post(
                f"/api/v1/requests/{no_gps['id']}/recommendations", headers=customer, json={}
            ).json()["data"]["recommendations"]
        )
        == 1
    )
    # Booking rechecks coverage, not just the earlier recommendation result.
    payload = {
        "requestId": distant["id"],
        "workerId": professional["id"],
        "scheduledAt": distant["preferredAt"],
        "scheduledEndAt": (
            datetime.fromisoformat(distant["preferredAt"]) + timedelta(hours=2)
        ).isoformat(),
    }
    assert api.post("/api/v1/bookings", headers=customer, json=payload).status_code == 422
    booking(api, customer, nearby, professional)


@pytest.mark.parametrize(
    "patch",
    [
        {"latitude": 91},
        {"longitude": 181},
        {"latitude": None},
        {"serviceRadiusKm": 501},
        {"serviceRadiusKm": None},
    ],
)
def test_invalid_partial_worker_location_does_not_change_saved_profile(api, patch):
    headers, professional, _ = worker(api, latitude=6.9271, longitude=79.8612, serviceRadiusKm=10)
    assert api.patch("/api/v1/worker/profile", headers=headers, json=patch).status_code == 422
    saved = api.get("/api/v1/worker/profile", headers=headers).json()["data"]
    assert saved["latitude"] == professional["latitude"]
    assert saved["approvalStatus"] == "approved"


def test_booking_end_deadline_validation_and_concurrent_worker_overlap(api):
    customer, _ = account(api)
    _, professional, _ = worker(api)
    first = service_request(api, customer)
    second = service_request(api, customer, preferredAt=first["preferredAt"])
    start = datetime.fromisoformat(first["preferredAt"])
    payload = {
        "workerId": professional["id"],
        "scheduledAt": start.isoformat(),
        "scheduledEndAt": (start + timedelta(hours=2)).isoformat(),
    }
    for invalid in [
        {"scheduledEndAt": start.isoformat()},
        {"deadlineAt": (start + timedelta(hours=1)).isoformat()},
    ]:
        assert (
            api.post(
                "/api/v1/bookings",
                headers=customer,
                json={**payload, "requestId": first["id"], **invalid},
            ).status_code
            == 422
        )
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(
            executor.map(
                lambda req: api.post(
                    "/api/v1/bookings", headers=customer, json={**payload, "requestId": req["id"]}
                ),
                [first, second],
            )
        )
    assert sorted(response.status_code for response in responses) == [201, 409]
    saved = next(response.json()["data"] for response in responses if response.status_code == 201)
    assert saved["deadlineAt"] == saved["scheduledEndAt"]
    remaining = second if saved["requestId"] == first["id"] else first
    response = api.post(
        "/api/v1/bookings",
        headers=customer,
        json={
            **payload,
            "requestId": remaining["id"],
            "scheduledAt": (start + timedelta(hours=2)).isoformat(),
            "scheduledEndAt": (start + timedelta(hours=4)).isoformat(),
        },
    )
    assert response.status_code == 201


def test_customer_confirmation_dispute_and_review_authorization(api):
    customer, _ = account(api)
    stranger, _ = account(api)
    headers, professional, _ = worker(api)
    record = booking(api, customer, service_request(api, customer), professional)
    bid = record["id"]
    for status in ["accepted", "in_progress", "awaiting_confirmation"]:
        assert transition(api, headers, bid, status).status_code == 200
    assert transition(api, headers, bid, "completed").status_code == 409
    assert transition(api, stranger, bid, "completed").status_code == 404
    assert (
        api.post(
            f"/api/v1/bookings/{bid}/review",
            headers=customer,
            json={"rating": 5, "comment": "Finished work."},
        ).status_code
        == 409
    )
    assert (
        api.get("/api/v1/worker/performance", headers=headers).json()["data"]["completedJobs"] == 0
    )
    assert transition(api, customer, bid, "in_progress").status_code == 422
    response = transition(api, customer, bid, "in_progress", "The pipe still leaks.")
    assert response.json()["data"]["reportedCompletedAt"] is None
    reported = transition(api, headers, bid, "awaiting_confirmation").json()["data"][
        "reportedCompletedAt"
    ]
    confirmed = transition(api, customer, bid, "completed").json()["data"]
    assert confirmed["reportedCompletedAt"] == reported
    assert confirmed["confirmedAt"] is not None
    assert transition(api, customer, bid, "completed").status_code == 409
    assert (
        api.get("/api/v1/worker/performance", headers=headers).json()["data"]["completedJobs"] == 1
    )


def test_complaints_are_owned_unique_and_admin_decisions_are_final(api):
    admin, _ = account(api, "admin")
    customer, _ = account(api)
    stranger, _ = account(api)
    headers, professional, _ = worker(api)
    record = booking(api, customer, service_request(api, customer), professional)
    path = f"/api/v1/bookings/{record['id']}/complaint"
    reason = {"reason": "The repair caused another leak and needs investigation."}
    assert api.post(path, headers=customer, json=reason).status_code == 409
    assert api.post(path, headers=stranger, json=reason).status_code == 404
    assert api.post(path, headers=headers, json=reason).status_code == 403
    transition(api, headers, record["id"], "accepted")
    transition(api, headers, record["id"], "in_progress")
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(
            executor.map(lambda _: api.post(path, headers=customer, json=reason), range(2))
        )
    assert sorted(response.status_code for response in responses) == [201, 409]
    complaint = next(
        response.json()["data"] for response in responses if response.status_code == 201
    )
    resolution_path = f"/api/v1/admin/complaints/{complaint['id']}/resolution"
    decision = {
        "status": "upheld",
        "resolution": "Both parties confirmed the unresolved repair damage.",
    }
    assert api.patch(resolution_path, headers=customer, json=decision).status_code == 403
    assert api.patch(resolution_path, headers=admin, json=decision).status_code == 200
    assert api.patch(resolution_path, headers=admin, json=decision).status_code == 409
    visible = api.get(f"/api/v1/bookings/{record['id']}", headers=headers).json()["data"][
        "complaint"
    ]
    assert visible["resolution"] == decision["resolution"] and visible["resolvedAt"] is not None
    with api.app.state.sessions() as db:
        assert (
            db.scalar(select(AuditEvent).where(AuditEvent.action == "complaint.resolved"))
            is not None
        )

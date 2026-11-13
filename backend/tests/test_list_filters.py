from datetime import UTC, datetime, timedelta

from tests.helpers import account, booking, service_request, transition, worker


def test_booking_filters_are_applied_before_pagination_and_preserve_ownership(api):
    customer, _ = account(api)
    other, _ = account(api)
    professional_headers, professional, _ = worker(api)
    ids = []
    for index in range(3):
        request = service_request(
            api,
            customer,
            title=f"Kitchen repair {index}",
            preferredAt=(datetime.now(UTC) + timedelta(days=index + 2)).isoformat(),
        )
        ids.append(booking(api, customer, request, professional)["id"])
    assert transition(api, customer, ids[0], "cancelled", "Plans changed today").status_code == 200
    params = {"status": "pending", "search": "KITCHEN", "perPage": 1}
    first = api.get("/api/v1/bookings", headers=customer, params=params).json()
    second = api.get("/api/v1/bookings", headers=customer, params={**params, "page": 2}).json()
    assert first["meta"]["total"] == 2
    assert first["meta"]["lastPage"] == 2
    assert {first["data"][0]["id"], second["data"][0]["id"]} == set(ids[1:])
    assert api.get("/api/v1/bookings", headers=other, params=params).json()["meta"]["total"] == 0
    assert (
        api.get("/api/v1/bookings", headers=professional_headers, params=params).json()["meta"][
            "total"
        ]
        == 2
    )
    assert (
        api.get("/api/v1/bookings", headers=customer, params={"search": "%"}).json()["data"] == []
    )
    assert (
        api.get("/api/v1/bookings", headers=customer, params={"status": "invalid"}).status_code
        == 422
    )
    active = api.get(
        "/api/v1/bookings", headers=customer, params={"group": "active", "order": "scheduled_asc"}
    ).json()["data"]
    assert [item["id"] for item in active] == ids[1:]
    assert (
        api.get("/api/v1/bookings", headers=customer, params={"group": "confirmed"}).json()["data"]
        == []
    )


def test_admin_search_and_ready_filter_use_database_pagination(api):
    admin, _ = account(api, "admin")
    _, ready, _ = worker(api, name="Ready Professional", approved=False)
    account(api, "worker", name="Incomplete Professional")
    worker(api, name="Approved Professional")
    result = api.get(
        "/api/v1/admin/workers",
        headers=admin,
        params={"pendingOnly": True, "search": "PROFESSIONAL", "perPage": 1},
    ).json()
    assert result["meta"]["total"] == 1
    assert result["data"][0]["id"] == ready["id"]
    assert (
        api.get("/api/v1/admin/workers", headers=admin, params={"search": "%"}).json()["data"] == []
    )
    assert (
        api.get("/api/v1/admin/workers", headers=admin, params={"search": "x" * 201}).status_code
        == 422
    )
    categories = api.get(
        "/api/v1/admin/categories", headers=admin, params={"search": "Plumbing", "perPage": 1}
    ).json()
    assert categories["meta"]["total"] == 1
    assert categories["data"][0]["label"] == "Plumbing"

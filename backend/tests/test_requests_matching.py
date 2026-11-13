# Check request ownership and rule-based matching without inventing model scores.

import pytest

from tests.helpers import account, request_payload, service_request, worker


@pytest.mark.parametrize(
    "changes",
    [
        {"title": "tiny"},
        {"description": "short"},
        {"town": " "},
        {"budgetLkr": 0},
        {"preferredAt": "2020-01-01T12:00:00+05:30"},
        {"preferredAt": "2099-01-01T12:00:00"},
        {"category": "Unknown service"},
        {"customerId": "forged"},
        {"title": None},
    ],
)
def test_request_validation_does_not_create_invalid_records(api, changes):
    headers, _ = account(api)
    response = api.post("/api/v1/requests", headers=headers, json=request_payload(**changes))
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "validation_error"
    assert api.get("/api/v1/requests", headers=headers).json()["meta"]["total"] == 0


def test_requests_are_private_editable_and_accept_manual_category_when_model_is_missing(api):
    headers, _ = account(api)
    other, _ = account(api)
    request = service_request(api, headers, category=None)
    path = f"/api/v1/requests/{request['id']}"
    assert api.get(path, headers=other).status_code == 404
    assert api.patch(path, headers=other, json={"title": "Different request"}).status_code == 404
    classification = api.post(path + "/classify", headers=headers)
    assert classification.status_code == 503
    assert classification.json()["error"]["code"] == "model_unavailable"
    assert api.post(path + "/recommendations", headers=headers, json={}).status_code == 422
    assert api.patch(path, headers=headers, json={"category": "Plumbing"}).status_code == 200
    saved = api.get(path, headers=headers).json()["data"]
    assert saved["category"] == "Plumbing"
    assert saved["preferredAt"].endswith("Z")
    assert api.get("/api/v1/requests/missing", headers=headers).status_code == 404


def test_matching_filters_category_town_availability_price_and_never_fakes_scores(api):
    customer, _ = account(api)
    _, eligible, _ = worker(api, name="Eligible Worker")
    worker(api, name="Different Category", categories=["Electrical"])
    worker(api, name="Different Town", serviceTowns=["Kandy"])
    worker(api, name="Unavailable Worker", available=False)
    worker(api, name="Expensive Worker", rateLkr=9000)
    request = service_request(api, customer)
    response = api.post(
        f"/api/v1/requests/{request['id']}/recommendations",
        headers=customer,
        json={"maxRate": 3000},
    )
    assert response.status_code == 200
    result = response.json()["data"]
    assert result["source"] == "rule_based"
    assert [entry["workerId"] for entry in result["recommendations"]] == [eligible["id"]]
    entry = result["recommendations"][0]
    assert entry["matchScore"] is None
    assert entry["categorySkillScore"] is None
    assert entry["reliabilityProbability"] is None
    assert any("not an AI ranking" in reason for reason in entry["reasons"])
    directory = api.get(
        "/api/v1/workers",
        params={
            "category": "Plumbing",
            "town": "COLOMBO",
            "available": True,
            "maxRate": 3000,
            "perPage": 1,
        },
    )
    assert directory.status_code == 200
    assert directory.json()["meta"]["total"] == 1
    assert directory.json()["data"][0]["id"] == eligible["id"]
    assert "email" not in directory.text
    assert api.get("/api/v1/workers", params={"search": "%"}).json()["meta"]["total"] == 0
    assert api.get("/api/v1/workers", params={"page": 0}).status_code == 422

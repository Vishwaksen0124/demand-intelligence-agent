from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def _customer_headers() -> dict[str, str]:
    return {
        "X-User-Id": "cust-e2e-1",
        "X-User-Role": "CUSTOMER",
        "X-User-Email": "customer@example.com",
    }


def _employee_headers() -> dict[str, str]:
    return {
        "X-User-Id": "emp-e2e-1",
        "X-User-Role": "EMPLOYEE",
        "X-User-Email": "employee@example.com",
    }


def test_customer_to_employee_request_lifecycle():
    products = client.get("/products").json()
    product_id = products[0]["id"]

    created = client.post(
        "/requests",
        headers=_customer_headers(),
        json={
            "region": {
                "country": "India",
                "state": "Karnataka",
                "city": "Bangalore",
                "region": "South India",
                "store_id": "BLR-042",
            },
            "forecast_horizon_days": 7,
            "inventory": [
                {
                    "product_id": product_id,
                    "product_name": products[0]["name"],
                    "current_stock": 32,
                    "unit_cost": products[0]["unit_cost"],
                    "supplier_lead_time_days": 2,
                    "minimum_order_quantity": 10,
                }
            ],
            "historical_sales_source": "S3",
            "constraints": {"max_purchase_budget": 50000},
        },
    )
    assert created.status_code == 200
    request_id = created.json()["request_id"]

    submitted = client.post(f"/requests/{request_id}/submit", headers=_customer_headers())
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "SUBMITTED"

    request_detail = client.get(f"/requests/{request_id}", headers=_customer_headers())
    assert request_detail.status_code == 200
    assert request_detail.json()["created_by"] == "cust-e2e-1"

    analysis = client.post(f"/requests/{request_id}/analyze", headers=_employee_headers())
    assert analysis.status_code == 200
    recommendations = analysis.json()["recommendations"]
    assert len(recommendations) == 1
    recommendation_id = recommendations[0]["recommendation_id"]

    forecast = client.get(f"/requests/{request_id}/forecast", headers=_customer_headers())
    assert forecast.status_code == 200
    assert len(forecast.json()["forecasts"]) == 1

    review_queue = client.get("/requests", headers=_employee_headers())
    assert review_queue.status_code == 200
    assert any(item["request_id"] == request_id for item in review_queue.json()["requests"])

    modified = client.post(
        f"/recommendations/{recommendation_id}/modify",
        headers=_employee_headers(),
        json={
            "quantity": max(recommendations[0]["ai_quantity"] - 5, 0),
            "status": "REVIEW_REQUIRED",
            "priority": "HIGH",
            "reason": "Supplier delivery lands tomorrow",
        },
    )
    assert modified.status_code == 200
    assert modified.json()["modified"] is True
    assert modified.json()["manager_quantity"] == max(recommendations[0]["ai_quantity"] - 5, 0)

    approved = client.post(f"/recommendations/{recommendation_id}/approve", headers=_employee_headers())
    assert approved.status_code == 200
    assert approved.json()["approval_status"] == "APPROVED"

    audit = client.get(f"/requests/{request_id}/audit", headers=_customer_headers())
    assert audit.status_code == 200
    actions = [item["action"] for item in audit.json()["events"]]
    assert "REQUEST_CREATED" in actions
    assert "REQUEST_SUBMITTED" in actions
    assert "REQUEST_ANALYZING" in actions
    assert "AI_RECOMMENDATION_GENERATED" in actions
    assert "RECOMMENDATION_MODIFIED" in actions
    assert "RECOMMENDATION_APPROVED" in actions
    assert [event["timestamp"] for event in audit.json()["events"]] == sorted(event["timestamp"] for event in audit.json()["events"])

    recommendations_view = client.get(f"/requests/{request_id}/recommendations", headers=_customer_headers())
    assert recommendations_view.status_code == 200
    recommendation_view = recommendations_view.json()["recommendations"][0]
    assert recommendation_view["approval_status"] == "APPROVED"
    assert recommendation_view["ai_quantity"] != recommendation_view["manager_quantity"]
    assert recommendation_view["reviewed_by"] == "emp-e2e-1"
    employee_queue = client.get("/employee/requests?status=APPROVED", headers=_employee_headers())
    assert employee_queue.status_code == 200
    assert not any(item["request_id"] == request_id for item in employee_queue.json()["requests"])

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_products_and_analysis():
    products = client.get("/products").json()
    assert len(products) == 20

    product_id = products[0]["id"]
    detail = client.get(f"/products/{product_id}")
    assert detail.status_code == 200

    forecast = client.post("/forecast", json={"product_id": product_id})
    assert forecast.status_code == 200
    assert len(forecast.json()["daily_forecast"]) == 7

    analysis = client.post("/analyze", json={"product_id": product_id})
    assert analysis.status_code == 200
    assert analysis.json()["decision"]["status"] in {"NORMAL", "WATCH", "REORDER", "URGENT"}


def test_dashboard_analysis():
    response = client.post("/analyze", json={})
    assert response.status_code == 200
    body = response.json()
    assert body["total_products"] == 20
    assert len(body["products"]) == 20


def test_analytics_summary():
    response = client.get("/analytics", headers={"X-User-Id": "emp-analytics", "X-User-Role": "EMPLOYEE"})
    assert response.status_code == 200
    body = response.json()
    assert body["total_products"] == 20
    assert "products" in body


def test_employee_analytics_contract_and_customer_denial():
    employee = {"X-User-Id": "emp-analytics", "X-User-Role": "EMPLOYEE"}
    response = client.get("/analytics?region=South%20India&store=BLR-042", headers=employee)
    assert response.status_code == 200
    body = response.json()
    for key in ("total_products", "stockout_risk", "overstock", "pending_approvals", "total_recommended_purchase_value", "approved_purchase_value", "modified_recommendations", "regional_demand_trends"):
        assert key in body
    assert client.get("/analytics", headers={"X-User-Id": "cust-analytics", "X-User-Role": "CUSTOMER"}).status_code == 403
    assert client.get("/alerts", headers=employee).status_code == 200

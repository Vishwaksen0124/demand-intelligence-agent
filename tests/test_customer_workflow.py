from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def headers(user="customer-a"):
    return {"X-User-Id": user, "X-User-Role": "CUSTOMER", "X-User-Email": f"{user}@example.com"}


def payload(product=None, stock=23):
    product = product or client.get("/products").json()[0]
    return {
        "region": {"country": "India", "state": "Karnataka", "city": "Bangalore", "region": "South India", "store_id": "BLR-042"},
        "forecast_horizon_days": 7,
        "inventory": [{"product_id": product["id"], "product_name": product["name"], "current_stock": stock, "unit_cost": product["unit_cost"], "supplier_lead_time_days": 2, "minimum_order_quantity": 5}],
        "historical_sales_source": "S3",
        "constraints": {"max_purchase_budget": 50000},
    }


def test_customer_creates_and_retrieves_own_request():
    response = client.post("/requests", headers=headers(), json=payload())
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "SUBMITTED"
    assert body["created_by"] == "customer-a"
    assert client.get(f"/requests/{body['request_id']}", headers=headers()).status_code == 200
    assert any(event["action"] == "REQUEST_CREATED" for event in client.get(f"/requests/{body['request_id']}/audit", headers=headers()).json()["events"])


def test_customer_cannot_retrieve_another_customers_request():
    request_id = client.post("/requests", headers=headers("customer-owner"), json=payload()).json()["request_id"]
    assert client.get(f"/requests/{request_id}", headers=headers("customer-other")).status_code == 403


def test_invalid_store_product_inventory_and_authentication():
    body = payload()
    body["region"]["store_id"] = "missing-store"
    assert client.post("/requests", headers=headers(), json=body).status_code == 422
    body = payload(); body["inventory"][0]["product_id"] = "missing-product"
    assert client.post("/requests", headers=headers(), json=body).status_code == 422
    body = payload(stock=-1)
    assert client.post("/requests", headers=headers(), json=body).status_code == 422
    assert client.post("/requests", json=payload()).status_code == 401
    assert client.post("/requests", headers=headers(), json={}).status_code == 422

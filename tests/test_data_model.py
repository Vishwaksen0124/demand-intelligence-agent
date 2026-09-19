from datetime import date

import pytest

from app.core.data import DataRepository
from app.core.models import (AuditEvent, Forecast, Inventory, Product, Recommendation, Region, Sale, Store, UserRole, InventoryRequest)

def repo():
    r = DataRepository()
    r.put_region(Region(region_id="r1", country="India", state="KA", city="Bengaluru", region="South India", store_id="s1"))
    r.put_store(Store(store_id="s1", name="Central", region="r1"))
    r.put_product(Product(id="p1", name="Milk", category="Dairy", current_inventory=10, supplier_lead_time_days=2, minimum_order_quantity=5, unit_cost=2))
    return r

def request():
    return InventoryRequest(request_id="req-1", created_by="u1", created_by_role=UserRole.CUSTOMER, region=Region(region_id="r1", country="India", state="KA", city="Bengaluru", region="South India", store_id="s1"))

def test_creating_and_retrieving_store_specific_inventory():
    r = repo(); r.put_inventory(Inventory(store_id="s1", product_id="p1", current_quantity=7))
    assert r.get_inventory("s1", "p1").current_quantity == 7
    assert r.list_inventory(store_id="s1", product_id="p1")[0].store_id == "s1"
    with pytest.raises(ValueError): r.put_inventory(Inventory(store_id="missing", product_id="p1", current_quantity=1))

def test_creating_and_retrieving_request():
    r = repo(); item = r.put_request(request())
    assert r.get_request("req-1").created_by == item.created_by

def test_storing_forecast_and_recommendation():
    r = repo(); r.put_request(request())
    forecast = r.put_forecast(Forecast(forecast_id="f1", request_id="req-1", product_id="p1", forecast_horizon=7, forecast_quantity=22, trend="UP", confidence=.8))
    recommendation = r.put_recommendation(Recommendation(recommendation_id="rec-1", request_id="req-1", product_id="p1", ai_quantity=10, ai_status="REORDER", ai_priority="HIGH", ai_reason="low stock", ai_confidence=.8))
    assert r.get_forecasts("req-1") == [forecast]
    assert r.get_recommendations("req-1") == [recommendation]
    assert recommendation.manager_quantity is None

def test_storing_audit_event_and_historical_sales():
    r = repo(); r.put_sale(Sale(sales_id="sale-1", store_id="s1", region_id="r1", product_id="p1", date=date(2026, 1, 1), quantity=4))
    event = r.put_audit_event(AuditEvent(event_id="e1", request_id="req-1", user_id="u1", user_role=UserRole.CUSTOMER, action="REQUEST_CREATED"))
    assert r.list_sales(store_id="s1", region_id="r1", product_id="p1")[0].quantity == 4
    assert r.get_audit_events("req-1") == [event]


def test_regional_and_store_sales_filtering():
    from datetime import date
    from app.core.models import Sale
    r = repo()
    r.put_sale(Sale(sales_id="in-scope", store_id="s1", region_id="r1", product_id="p1", date=date(2026, 1, 1), quantity=5))
    r.put_sale(Sale(sales_id="other-store", store_id="s2", region_id="r1", product_id="p1", date=date(2026, 1, 1), quantity=99))
    r.put_sale(Sale(sales_id="other-region", store_id="s1", region_id="r2", product_id="p1", date=date(2026, 1, 1), quantity=99))
    assert [item.sales_id for item in r.list_sales(region_id="r1", store_id="s1", product_id="p1")] == ["in-scope"]

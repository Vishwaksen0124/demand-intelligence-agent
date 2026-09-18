from __future__ import annotations

from app.core.catalog import get_history, get_product
from app.core.decision import decide
from app.core.forecast import calculate_forecast
from app.core.inventory import calculate_inventory


def test_deterministic_pipeline_produces_actionable_result():
    product = get_product("P002")
    history = get_history("P002")
    forecast = calculate_forecast(product.id, history)
    inventory = calculate_inventory(product, history, forecast)
    decision = decide(product, forecast, inventory)

    assert len(forecast.daily_forecast) == 7
    assert forecast.forecast_7_day > 0
    assert inventory.reorder_point >= inventory.safety_stock
    assert decision.status in {"NORMAL", "WATCH", "REORDER", "URGENT"}
    assert decision.recommended_order >= 0


def test_urgent_products_stay_orderable():
    product = get_product("P012")
    history = get_history("P012")
    forecast = calculate_forecast(product.id, history)
    inventory = calculate_inventory(product, history, forecast)

    assert inventory.target_stock >= product.current_inventory


def test_forecast_horizon_and_inventory_formulas():
    product = get_product("P002").model_copy(update={"current_inventory": 40, "supplier_lead_time_days": 2, "minimum_order_quantity": 1})
    history = get_history("P002")
    forecast = calculate_forecast(product.id, history, horizon_days=14)
    inventory = calculate_inventory(product, history, forecast)
    assert forecast.forecast_horizon == 14
    assert len(forecast.daily_forecast) == 14
    assert forecast.forecast_quantity == sum(forecast.daily_forecast)
    assert inventory.reorder_point == __import__("math").ceil(inventory.demand_during_lead_time + inventory.safety_stock)
    assert inventory.recommended_order_quantity >= 0

def test_zero_inventory_zero_sales_and_short_history_are_deterministic():
    from datetime import date
    from app.core.models import Product, SalesPoint
    product = Product(id="edge", name="Edge", category="Test", current_inventory=0, supplier_lead_time_days=3, minimum_order_quantity=2, unit_cost=1)
    history = [SalesPoint(date=date(2026, 1, 1), units=0)]
    forecast = calculate_forecast(product.id, history, horizon_days=7)
    inventory = calculate_inventory(product, history, forecast)
    assert forecast.forecast_quantity == 0
    assert inventory.average_daily_demand == 0
    assert inventory.days_until_stockout == float("inf")
    assert inventory.safety_stock == 0
    assert inventory.recommended_order_quantity == 0
    assert not inventory.stockout_risk

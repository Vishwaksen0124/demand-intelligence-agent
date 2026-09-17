from __future__ import annotations

from math import ceil, sqrt
from statistics import mean, pstdev

from .models import ForecastResult, InventoryResult, Product, SalesPoint


def calculate_inventory(product: Product, history: list[SalesPoint], forecast: ForecastResult) -> InventoryResult:
    values = [point.units for point in history]
    average_daily_demand = float(mean(values[-14:]) if values else 0.0)
    demand_during_lead_time = average_daily_demand * product.supplier_lead_time_days
    lead_time_volatility = pstdev(values[-14:]) if len(values) > 1 else 0.0
    demand_variability = lead_time_volatility
    z_factor = 1.65 if forecast.confidence >= 0.8 else 1.28 if forecast.confidence >= 0.65 else 0.84
    safety_stock = int(ceil(lead_time_volatility * sqrt(product.supplier_lead_time_days) * z_factor))
    reorder_point = int(ceil(demand_during_lead_time + safety_stock))
    horizon_demand = forecast.forecast_quantity or forecast.forecast_7_day
    target_stock = int(ceil(max(average_daily_demand, horizon_demand / max(forecast.forecast_horizon, 1)) * max(product.supplier_lead_time_days + forecast.forecast_horizon, 14)))
    recommended_order_quantity = max(0, target_stock - product.current_inventory)
    if 0 < recommended_order_quantity < product.minimum_order_quantity:
        recommended_order_quantity = product.minimum_order_quantity
    days_until_stockout = float("inf") if average_daily_demand == 0 else product.current_inventory / average_daily_demand
    overstock_quantity = max(0, product.current_inventory - target_stock)
    stockout_risk = average_daily_demand > 0 and product.current_inventory <= reorder_point
    overstock_risk = overstock_quantity > 0

    return InventoryResult(
        product_id=product.id,
        demand_variability=demand_variability,
        overstock_quantity=overstock_quantity,
        stockout_risk=stockout_risk,
        overstock_risk=overstock_risk,
        average_daily_demand=average_daily_demand,
        demand_during_lead_time=demand_during_lead_time,
        safety_stock=safety_stock,
        reorder_point=reorder_point,
        recommended_order_quantity=recommended_order_quantity,
        days_until_stockout=days_until_stockout,
        target_stock=target_stock,
    )

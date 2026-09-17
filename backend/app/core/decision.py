from __future__ import annotations

from .models import DecisionResult, ForecastResult, InventoryResult, Product


def decide(product: Product, forecast: ForecastResult, inventory: InventoryResult) -> DecisionResult:
    if inventory.overstock_risk and not inventory.stockout_risk:
        status = "OVERSTOCK"
        priority = "LOW"
    elif inventory.days_until_stockout <= 3 or (inventory.recommended_order_quantity >= product.minimum_order_quantity and inventory.days_until_stockout <= 7):
        status = "URGENT"
        priority = "HIGH"
    elif inventory.reorder_point >= product.current_inventory:
        status = "REORDER"
        priority = "HIGH"
    elif inventory.days_until_stockout <= 21 or forecast.trend > 0.1:
        status = "WATCH"
        priority = "MEDIUM"
    else:
        status = "NORMAL"
        priority = "LOW"

    risks: list[str] = []
    if forecast.trend > 0.1:
        risks.append("Demand is rising")
    if inventory.days_until_stockout <= product.supplier_lead_time_days:
        risks.append("Stock may run out before replenishment")
    if inventory.recommended_order_quantity == 0 and inventory.days_until_stockout > 30:
        risks.append("Inventory is comfortably above target")

    reason = (
        f"{status} because stock covers {inventory.days_until_stockout:.1f} days, "
        f"reorder point is {inventory.reorder_point}, and demand over {forecast.forecast_horizon} days is {forecast.forecast_quantity:.1f}."
    )

    return DecisionResult(
        product_id=product.id,
        status=status,
        priority=priority,
        recommended_order=inventory.recommended_order_quantity,
        reason=reason,
        risks=risks,
        confidence=min(forecast.confidence, 0.95),
    )

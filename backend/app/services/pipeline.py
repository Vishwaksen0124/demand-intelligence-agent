from __future__ import annotations

from ..aws.bedrock import explain_with_bedrock
from ..aws.storage import AnalysisStore
from ..core.catalog import get_history, get_product, list_products
from ..core.decision import decide
from ..core.forecast import calculate_forecast
from ..core.inventory import calculate_inventory
from ..core.models import AnalysisResponse, DashboardResponse, ProductSummary


class AnalyticsService:
    def __init__(self, store: AnalysisStore | None = None) -> None:
        self.store = store or AnalysisStore()

    def analyze_product(self, product_id: str) -> AnalysisResponse:
        product = get_product(product_id)
        history = get_history(product_id)
        forecast = calculate_forecast(product_id, history)
        inventory = calculate_inventory(product, history, forecast)
        decision = decide(product, forecast, inventory)
        fallback = (
            f"{decision.status} because forecasted demand is {forecast.forecast_7_day:.1f} units over 7 days "
            f"and stock covers {inventory.days_until_stockout:.1f} days."
        )
        explanation = explain_with_bedrock(
            {
                "fallback": fallback,
                "context": {
                    "product": product.model_dump(),
                    "forecast": forecast.model_dump(),
                    "inventory": inventory.model_dump(),
                    "decision": decision.model_dump(),
                },
            }
        )
        response = AnalysisResponse(product=product, history=history, forecast=forecast, inventory=inventory, decision=decision, explanation=explanation)
        self.store.save(response.model_dump(mode="json"))
        return response

    def analyze_all(self) -> DashboardResponse:
        analyses = [self.analyze_product(product.id) for product in list_products()]
        summaries = [
            ProductSummary(
                product=item.product,
                current_inventory=item.product.current_inventory,
                forecast_7_day=item.forecast.forecast_7_day,
                days_until_stockout=item.inventory.days_until_stockout,
                risk=item.decision.status,
                recommended_order=item.decision.recommended_order,
                priority=item.decision.priority,
            )
            for item in analyses
        ]
        stockout_risk = sum(1 for item in analyses if item.decision.status in {"WATCH", "REORDER", "URGENT"})
        reorder_required = sum(1 for item in analyses if item.decision.status in {"REORDER", "URGENT"})
        overstock = sum(1 for item in analyses if item.inventory.recommended_order_quantity == 0 and item.inventory.days_until_stockout > 30)
        total_recommended_purchase_value = sum(item.decision.recommended_order * item.product.unit_cost for item in analyses)
        return DashboardResponse(
            total_products=len(analyses),
            stockout_risk=stockout_risk,
            reorder_required=reorder_required,
            overstock=overstock,
            total_recommended_purchase_value=round(total_recommended_purchase_value, 2),
            products=summaries,
        )

    def alerts(self) -> list[dict]:
        return self.store.list_alerts()

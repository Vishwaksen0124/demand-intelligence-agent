from __future__ import annotations

import logging
from uuid import uuid4

from ..core.alerts import ALERT_REPOSITORY, AlertRepository
from ..core.catalog import get_history, list_products
from ..core.decision import decide
from ..core.forecast import calculate_forecast
from ..core.inventory import calculate_inventory
from ..core.models import InventoryAlert
from ..aws.storage import AnalysisStore

logger = logging.getLogger(__name__)

MONITORED_STORES = (
    {"store_id": "BLR-042", "region_id": "south-india", "region": "South India"},
    {"store_id": "SJC-101", "region_id": "west-coast", "region": "West Coast"},
)


class InventoryMonitoringService:
    def __init__(self, alerts: AlertRepository | None = None, store: AnalysisStore | None = None):
        self.alerts = alerts or ALERT_REPOSITORY
        self.store = store or AnalysisStore()

    def run(self) -> list[InventoryAlert]:
        generated = []
        for store in MONITORED_STORES:
            for product in list_products():
                history = get_history(product.id)
                forecast = calculate_forecast(product.id, history, horizon_days=7)
                inventory = calculate_inventory(product, history, forecast)
                decision = decide(product, forecast, inventory)
                if decision.status not in {"WATCH", "REORDER", "URGENT", "OVERSTOCK"}:
                    continue
                alert = InventoryAlert(
                    alert_id=f"ALT-{store['store_id']}-{product.id}-{uuid4().hex[:8].upper()}",
                    store_id=store["store_id"], region_id=store["region_id"], product_id=product.id,
                    status=decision.status, priority=decision.priority,
                    current_inventory=product.current_inventory, recommended_order=decision.recommended_order,
                    reason=decision.reason,
                )
                self.alerts.save(alert)
                self.store.save_alert(alert.model_dump(mode="json"))
                generated.append(alert)
        logger.info("inventory_monitoring_completed alerts=%d stores=%d", len(generated), len(MONITORED_STORES))
        return generated

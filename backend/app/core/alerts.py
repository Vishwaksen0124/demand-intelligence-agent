from __future__ import annotations

from .models import InventoryAlert


class AlertRepository:
    def __init__(self):
        self._alerts: dict[str, InventoryAlert] = {}

    def save(self, alert: InventoryAlert) -> InventoryAlert:
        self._alerts[alert.alert_id] = alert
        return alert

    def list(self) -> list[InventoryAlert]:
        return sorted(self._alerts.values(), key=lambda item: item.created_at, reverse=True)

    def clear(self) -> None:
        self._alerts.clear()


ALERT_REPOSITORY = AlertRepository()

from app.core.alerts import AlertRepository
from app.services.monitoring import InventoryMonitoringService


def test_monitoring_generates_employee_alerts_without_approval():
    repository = AlertRepository()
    service = InventoryMonitoringService(alerts=repository)
    alerts = service.run()
    assert alerts
    assert all(item.status in {"WATCH", "REORDER", "URGENT", "OVERSTOCK"} for item in alerts)
    assert all(item.recommended_order >= 0 for item in alerts)
    assert repository.list()


def test_scheduled_lambda_invokes_monitoring(monkeypatch):
    import app.main as main

    calls = []

    class FakeMonitor:
        def run(self):
            calls.append(True)
            return [object(), object()]

    monkeypatch.setattr(main, "InventoryMonitoringService", FakeMonitor)
    result = main.lambda_handler({"source": "aws.events"}, None)
    assert result == {"statusCode": 200, "body": '{"status":"monitored","alerts":2}'}
    assert calls == [True]

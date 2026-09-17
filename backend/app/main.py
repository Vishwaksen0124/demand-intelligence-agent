from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
try:
    from mangum import Mangum
except ImportError:  # Local test environments may not install Lambda extras.
    Mangum = None

from .api.routes import router
from .services.pipeline import AnalyticsService
from .services.monitoring import InventoryMonitoringService


app = FastAPI(title="Demand Intelligence Agent")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)

handler = Mangum(app) if Mangum else app


def lambda_handler(event, context):
    if isinstance(event, dict) and event.get("source") == "aws.events":
        alerts = InventoryMonitoringService().run()
        return {"statusCode": 200, "body": f'{{"status":"monitored","alerts":{len(alerts)}}}'}
    return handler(event, context)

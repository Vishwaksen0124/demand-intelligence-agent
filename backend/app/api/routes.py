from __future__ import annotations

import logging
import csv
import io
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from pydantic import BaseModel, Field

from ..core.catalog import get_history, get_product, list_products
from ..core.alerts import ALERT_REPOSITORY
from ..core.decision import decide
from ..core.forecast import calculate_forecast
from ..core.inventory import calculate_inventory
from ..core.regional import sales_to_history
from ..aws import bedrock
from ..aws.storage import AnalysisStore
from ..core.models import AuditEvent, DecisionAgentResponse, Forecast, HistoricalSalesUpload, InventoryItem, InventoryRequest, Recommendation, Region, UserRole, SalesPoint
from ..core.permissions import can_modify_recommendation, can_view_request
from ..core.requests import REQUEST_REPOSITORY
from .dependencies import IdentityContext, require_roles
from ..services.pipeline import AnalyticsService


router = APIRouter()
service = AnalyticsService()
analysis_store = AnalysisStore()
logger = logging.getLogger(__name__)


class ProductRequest(BaseModel):
    product_id: str = Field(min_length=1)


class AnalyzeRequest(BaseModel):
    product_id: str | None = None


class CreateRequestBody(BaseModel):
    region: Region
    forecast_horizon_days: int = Field(default=7, ge=1)
    inventory: list[InventoryItem] = Field(default_factory=list)
    historical_sales_source: str = Field(default="S3")
    historical_sales_upload: HistoricalSalesUpload | None = None
    constraints: dict = Field(default_factory=dict)


class ModifyRecommendationBody(BaseModel):
    quantity: int | None = Field(default=None, ge=0)
    status: str | None = None
    priority: str | None = None
    reason: str | None = None


class RejectRecommendationBody(BaseModel):
    reason: str = Field(min_length=1)


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


REGION_CATALOG = [
    {"region_id": "south-india", "country": "India", "state": "Karnataka", "city": "Bangalore", "region": "South India", "store_id": "BLR-042"},
    {"region_id": "west-coast", "country": "United States", "state": "California", "city": "San Jose", "region": "West Coast", "store_id": "SJC-101"},
]
STORE_CATALOG = [
    {"store_id": "BLR-042", "region_id": "south-india", "name": "Bangalore Central", "region": "South India", "city": "Bangalore", "state": "Karnataka", "country": "India", "location": "Bangalore", "active": True},
    {"store_id": "SJC-101", "region_id": "west-coast", "name": "San Jose Market", "region": "West Coast", "city": "San Jose", "state": "California", "country": "United States", "location": "San Jose", "active": True},
]


@router.get("/regions")
def regions() -> dict:
    return {"regions": REGION_CATALOG}


@router.get("/stores")
def stores() -> dict:
    return {"stores": STORE_CATALOG}


@router.get("/products")
def products() -> list[dict]:
    return [product.model_dump() for product in list_products()]


@router.get("/products/{product_id}")
def product_detail(product_id: str) -> dict:
    try:
        product = get_product(product_id)
        history = [point.model_dump() for point in get_history(product_id)]
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Product not found") from exc
    return {"product": product.model_dump(), "history": history}


@router.post("/forecast")
def forecast(request: ProductRequest) -> dict:
    try:
        history = get_history(request.product_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Product not found") from exc
    return calculate_forecast(request.product_id, history).model_dump()


@router.post("/inventory/analyze")
def inventory_analysis(request: ProductRequest) -> dict:
    try:
        product = get_product(request.product_id)
        history = get_history(request.product_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Product not found") from exc
    forecast_result = calculate_forecast(request.product_id, history)
    return calculate_inventory(product, history, forecast_result).model_dump()


@router.post("/decision")
def decision_analysis(request: ProductRequest) -> dict:
    try:
        product = get_product(request.product_id)
        history = get_history(request.product_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Product not found") from exc
    forecast_result = calculate_forecast(request.product_id, history)
    inventory_result = calculate_inventory(product, history, forecast_result)
    return decide(product, forecast_result, inventory_result).model_dump()


@router.post("/analyze")
def analyze(request: AnalyzeRequest | None = None) -> dict:
    if request and request.product_id:
        return service.analyze_product(request.product_id).model_dump()
    return service.analyze_all().model_dump()


@router.post("/historical-sales/upload")
async def upload_historical_sales(
    file: UploadFile = File(...),
    identity: IdentityContext = Depends(require_roles(UserRole.CUSTOMER, UserRole.EMPLOYEE, UserRole.ADMIN)),
) -> dict:
    if not file.filename or not file.filename.lower().endswith((".csv", ".json")):
        raise HTTPException(status_code=422, detail="Only CSV or JSON historical sales files are supported")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=422, detail="Historical sales file is empty")
    key = f"historical-sales/{identity.user_id}/{uuid4().hex}-{file.filename}"
    try:
        analysis_store.upload_historical_sales(key, content, file.content_type or "text/csv")
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"s3_key": key, "file_name": file.filename, "content_type": file.content_type, "bytes": len(content)}

@router.post("/requests")
def create_request(
    body: CreateRequestBody,
    identity: IdentityContext = Depends(require_roles(UserRole.CUSTOMER, UserRole.EMPLOYEE, UserRole.ADMIN)),
) -> dict:
    region = next((item for item in REGION_CATALOG if item["region"] == body.region.region), None)
    store = next((item for item in STORE_CATALOG if item["store_id"] == body.region.store_id), None)
    if not region:
        raise HTTPException(status_code=422, detail="Invalid region")
    if not store or not store["active"]:
        raise HTTPException(status_code=422, detail="Invalid or inactive store")
    if store["region_id"] != region["region_id"] or store["city"] != body.region.city or store["state"] != body.region.state or store["country"] != body.region.country:
        raise HTTPException(status_code=422, detail="Store does not belong to the supplied region")
    if not body.inventory:
        raise HTTPException(status_code=422, detail="At least one inventory item is required")
    for item in body.inventory:
        try:
            product = get_product(item.product_id)
        except KeyError as exc:
            raise HTTPException(status_code=422, detail=f"Invalid product: {item.product_id}") from exc
        if item.product_name != product.name:
            raise HTTPException(status_code=422, detail=f"Product name does not match product_id: {item.product_id}")
    request = InventoryRequest(
        request_id=f"REQ-{uuid4().hex[:8].upper()}",
        created_by=identity.user_id,
        created_by_role=identity.role,
        region=body.region,
        forecast_horizon_days=body.forecast_horizon_days,
        inventory=body.inventory,
        historical_sales_source=body.historical_sales_source,
        historical_sales_upload=body.historical_sales_upload,
        constraints=body.constraints,
    )
    REQUEST_REPOSITORY.create_request(request)
    # Customer creation is a submission, not a draft. The repository records both lifecycle events.
    submitted = REQUEST_REPOSITORY.submit_request(request.request_id, user_id=identity.user_id, user_role=identity.role)
    return submitted.model_dump(mode="json")


@router.post("/requests/{request_id}/submit")
def submit_request(
    request_id: str,
    identity: IdentityContext = Depends(require_roles(UserRole.CUSTOMER, UserRole.EMPLOYEE, UserRole.ADMIN)),
) -> dict:
    try:
        existing = REQUEST_REPOSITORY.get_request(request_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Request not found") from exc
    if not can_view_request(identity.role, existing.created_by, identity.user_id):
        raise HTTPException(status_code=403, detail="Forbidden")
    try:
        request = REQUEST_REPOSITORY.submit_request(request_id, user_id=identity.user_id, user_role=identity.role)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Request not found") from exc
    return request.model_dump(mode="json")


@router.get("/requests")
def list_requests(identity: IdentityContext = Depends(require_roles(UserRole.CUSTOMER, UserRole.EMPLOYEE, UserRole.ADMIN))) -> dict:
    if identity.role in {UserRole.EMPLOYEE, UserRole.ADMIN}:
        requests = REQUEST_REPOSITORY.list_requests()
    else:
        requests = REQUEST_REPOSITORY.list_requests(created_by=identity.user_id)
    result = []
    for item in requests:
        payload = item.model_dump(mode="json")
        recommendations = REQUEST_REPOSITORY.list_recommendations(item.request_id)
        payload["urgent_risks"] = sum(1 for recommendation in recommendations if recommendation.ai_status == "URGENT")
        result.append(payload)
    return {"requests": result}


@router.get("/employee/requests")
def employee_requests(
    region: str | None = None, city: str | None = None, store: str | None = None,
    status: str | None = None, priority: str | None = None,
    identity: IdentityContext = Depends(require_roles(UserRole.EMPLOYEE, UserRole.ADMIN)),
) -> dict:
    requests = REQUEST_REPOSITORY.list_requests(region=region, store_id=store, status=status, priority=priority)
    if city:
        requests = [item for item in requests if item.region.city == city]
    review_statuses = {"SUBMITTED", "ANALYZING", "REVIEW_REQUIRED", "MODIFIED"}
    requests = [item for item in requests if item.status in review_statuses]
    return {"requests": [item.model_dump(mode="json") for item in requests]}


@router.get("/requests/{request_id}")
def get_request(
    request_id: str,
    identity: IdentityContext = Depends(require_roles(UserRole.CUSTOMER, UserRole.EMPLOYEE, UserRole.ADMIN)),
) -> dict:
    try:
        request = REQUEST_REPOSITORY.get_request(request_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Request not found") from exc
    if not can_view_request(identity.role, request.created_by, identity.user_id):
        raise HTTPException(status_code=403, detail="Forbidden")
    return request.model_dump(mode="json")


def _history_for_request(request: InventoryRequest, product_id: str):
    upload = request.historical_sales_upload
    if upload and upload.s3_key:
        try:
            raw = analysis_store.read_object(upload.s3_key).decode("utf-8")
            rows = csv.DictReader(io.StringIO(raw))
            points = []
            for row in rows:
                if row.get("product_id") != product_id:
                    continue
                points.append(SalesPoint(date=row["date"], units=int(row.get("quantity", row.get("units", 0)))))
            if points:
                return points
        except (KeyError, ValueError, UnicodeDecodeError) as exc:
            logger.warning("Historical sales read failed for %s: %s", upload.s3_key, exc)
    region_id = request.region.region_id or request.region.region
    scoped_sales = REQUEST_REPOSITORY.list_sales(region_id=region_id, store_id=request.region.store_id, product_id=product_id)
    return sales_to_history(scoped_sales) if scoped_sales else get_history(product_id)


@router.post("/requests/{request_id}/analyze")
def analyze_request(
    request_id: str,
    identity: IdentityContext = Depends(require_roles(UserRole.EMPLOYEE, UserRole.ADMIN)),
) -> dict:
    try:
        request = REQUEST_REPOSITORY.get_request(request_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Request not found") from exc

    REQUEST_REPOSITORY.mark_request_analyzing(request_id, user_id=identity.user_id, user_role=identity.role)
    recommendations: list[Recommendation] = []

    for item in request.inventory:
        base_product = get_product(item.product_id)
        request_product = base_product.model_copy(update={
            "current_inventory": item.current_stock,
            "unit_cost": item.unit_cost,
            "supplier_lead_time_days": item.supplier_lead_time_days,
            "minimum_order_quantity": item.minimum_order_quantity,
        })
        history = _history_for_request(request, item.product_id)
        forecast_result = calculate_forecast(item.product_id, history, request.forecast_horizon_days)
        inventory_result = calculate_inventory(request_product, history, forecast_result)
        decision_result = decide(request_product, forecast_result, inventory_result)
        REQUEST_REPOSITORY.save_forecast(Forecast(
            forecast_id=f"FC-{uuid4().hex[:8].upper()}", request_id=request_id, product_id=item.product_id,
            forecast_horizon=request.forecast_horizon_days, forecast_quantity=forecast_result.forecast_quantity,
            trend=str(forecast_result.trend), confidence=forecast_result.confidence,
            calculation={"forecast": forecast_result.model_dump(mode="json"), "inventory": inventory_result.model_dump(mode="json"), "decision": decision_result.model_dump(mode="json")},
        ))
        REQUEST_REPOSITORY.record_event(AuditEvent(
            event_id=str(uuid4()), request_id=request_id, user_id=identity.user_id,
            user_role=identity.role, action="FORECAST_GENERATED",
            metadata={"product_id": item.product_id, "forecast_horizon": request.forecast_horizon_days},
        ))
        fallback_agent = DecisionAgentResponse(
            status=decision_result.status, priority=decision_result.priority,
            recommended_quantity=decision_result.recommended_order, reason=decision_result.reason,
            risks=decision_result.risks, confidence=decision_result.confidence,
        )
        facts = {
            "product": request_product.name, "region": request.region.city, "store_id": request.region.store_id,
            "current_stock": request_product.current_inventory,
            "forecast_quantity": forecast_result.forecast_quantity,
            "forecast_7_day": forecast_result.forecast_7_day,
            "average_daily_demand": inventory_result.average_daily_demand,
            "reorder_point": inventory_result.reorder_point, "safety_stock": inventory_result.safety_stock,
            "days_until_stockout": inventory_result.days_until_stockout,
            "deterministic_recommended_quantity": decision_result.recommended_order,
            "forecast_confidence": forecast_result.confidence,
            "supplier_lead_time_days": request_product.supplier_lead_time_days,
        }
        try:
            agent_result = bedrock.decide_with_bedrock(facts, fallback_agent)
        except bedrock.BedrockDecisionError as exc:
            logger.exception("Bedrock decision failed for request %s", request_id)
            REQUEST_REPOSITORY.submit_request(request_id, user_id=identity.user_id, user_role=identity.role)
            REQUEST_REPOSITORY.record_event(AuditEvent(
                event_id=str(uuid4()), request_id=request_id, user_id=identity.user_id,
                user_role=identity.role, action="AI_RECOMMENDATION_FAILED", metadata={"error": str(exc)},
            ))
            raise HTTPException(status_code=502, detail="Decision agent returned an invalid response") from exc
        recommendation = Recommendation(
            recommendation_id=f"REC-{uuid4().hex[:8].upper()}",
            request_id=request_id,
            product_id=item.product_id,
            ai_quantity=agent_result.recommended_quantity,
            ai_status=agent_result.status,
            ai_priority=agent_result.priority,
            ai_reason=agent_result.reason,
            ai_risks=agent_result.risks,
            ai_confidence=agent_result.confidence,
            calculation_snapshot={
                "forecast": forecast_result.model_dump(mode="json"),
                "inventory": inventory_result.model_dump(mode="json"),
                "decision": decision_result.model_dump(mode="json"),
            },
        )
        REQUEST_REPOSITORY.save_recommendation(recommendation, user_id=identity.user_id, user_role=identity.role)
        recommendations.append(recommendation)

    REQUEST_REPOSITORY.mark_request_review_required(request_id, user_id=identity.user_id, user_role=identity.role)
    return {
        "request": REQUEST_REPOSITORY.get_request(request_id).model_dump(mode="json"),
        "recommendations": [item.model_dump(mode="json") for item in recommendations],
    }


@router.get("/requests/{request_id}/forecast")
def request_forecast(
    request_id: str,
    identity: IdentityContext = Depends(require_roles(UserRole.CUSTOMER, UserRole.EMPLOYEE, UserRole.ADMIN)),
) -> dict:
    try:
        request = REQUEST_REPOSITORY.get_request(request_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Request not found") from exc
    if not can_view_request(identity.role, request.created_by, identity.user_id):
        raise HTTPException(status_code=403, detail="Forbidden")

    forecasts = []
    persisted = {item.product_id: item for item in REQUEST_REPOSITORY.list_forecasts(request_id)}
    for item in request.inventory:
        snapshot = persisted.get(item.product_id)
        if snapshot and snapshot.calculation:
            forecasts.append({"product_id": item.product_id, **snapshot.calculation})
            continue
        product = get_product(item.product_id).model_copy(update={
            "current_inventory": item.current_stock, "unit_cost": item.unit_cost,
            "supplier_lead_time_days": item.supplier_lead_time_days,
            "minimum_order_quantity": item.minimum_order_quantity,
        })
        history = _history_for_request(request, item.product_id)
        forecast_result = calculate_forecast(item.product_id, history, request.forecast_horizon_days)
        inventory_result = calculate_inventory(product, history, forecast_result)
        forecasts.append({"product_id": item.product_id, "forecast": forecast_result.model_dump(mode="json"), "inventory": inventory_result.model_dump(mode="json")})
    return {"request_id": request_id, "forecasts": forecasts}


@router.get("/requests/{request_id}/recommendations")
def request_recommendations(
    request_id: str,
    identity: IdentityContext = Depends(require_roles(UserRole.CUSTOMER, UserRole.EMPLOYEE, UserRole.ADMIN)),
) -> dict:
    try:
        request = REQUEST_REPOSITORY.get_request(request_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Request not found") from exc
    if not can_view_request(identity.role, request.created_by, identity.user_id):
        raise HTTPException(status_code=403, detail="Forbidden")
    return {"request_id": request_id, "recommendations": [item.model_dump(mode="json") for item in REQUEST_REPOSITORY.list_recommendations(request_id)]}


@router.post("/recommendations/{recommendation_id}/approve")
def approve_recommendation(
    recommendation_id: str,
    identity: IdentityContext = Depends(require_roles(UserRole.EMPLOYEE, UserRole.ADMIN)),
) -> dict:
    try:
        recommendation = REQUEST_REPOSITORY.approve_recommendation(recommendation_id, user_id=identity.user_id, user_role=identity.role)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Recommendation not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return recommendation.model_dump(mode="json")


@router.post("/recommendations/{recommendation_id}/reject")
def reject_recommendation(
    recommendation_id: str,
    body: RejectRecommendationBody,
    identity: IdentityContext = Depends(require_roles(UserRole.EMPLOYEE, UserRole.ADMIN)),
) -> dict:
    try:
        recommendation = REQUEST_REPOSITORY.reject_recommendation(recommendation_id, reason=body.reason, user_id=identity.user_id, user_role=identity.role)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Recommendation not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return recommendation.model_dump(mode="json")


@router.post("/recommendations/{recommendation_id}/modify")
def modify_recommendation(
    recommendation_id: str,
    body: ModifyRecommendationBody,
    identity: IdentityContext = Depends(require_roles(UserRole.EMPLOYEE, UserRole.ADMIN)),
) -> dict:
    if not can_modify_recommendation(identity.role):
        raise HTTPException(status_code=403, detail="Forbidden")
    try:
        recommendation = REQUEST_REPOSITORY.modify_recommendation(
            recommendation_id,
            manager_quantity=body.quantity,
            final_status=body.status,
            final_priority=body.priority,
            reason=body.reason,
            user_id=identity.user_id,
            user_role=identity.role,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Recommendation not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return recommendation.model_dump(mode="json")


@router.get("/requests/{request_id}/audit")
def request_audit(
    request_id: str,
    identity: IdentityContext = Depends(require_roles(UserRole.CUSTOMER, UserRole.EMPLOYEE, UserRole.ADMIN)),
) -> dict:
    try:
        request = REQUEST_REPOSITORY.get_request(request_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Request not found") from exc
    if not can_view_request(identity.role, request.created_by, identity.user_id):
        raise HTTPException(status_code=403, detail="Forbidden")
    return {"request_id": request_id, "events": [event.model_dump(mode="json") for event in REQUEST_REPOSITORY.list_audit_events(request_id)]}


def _analytics_payload(region: str | None = None, store: str | None = None) -> dict:
    dashboard = service.analyze_all().model_dump(mode="json")
    requests = REQUEST_REPOSITORY.list_requests(region=region, store_id=store)
    request_ids = {item.request_id for item in requests}
    recommendations = [item for item in REQUEST_REPOSITORY.list_all_recommendations() if item.request_id in request_ids]
    pending = sum(1 for item in recommendations if item.approval_status in {"REVIEW_REQUIRED", "MODIFIED"})
    modified = sum(1 for item in recommendations if item.modified)
    approved_value = 0.0
    for item in recommendations:
        if item.approval_status == "APPROVED":
            product = get_product(item.product_id)
            approved_value += (item.manager_quantity if item.manager_quantity is not None else item.ai_quantity) * product.unit_cost
    regional = {}
    for request in requests:
        key = request.region.region
        entry = regional.setdefault(key, {"region": key, "city": request.region.city, "store_id": request.region.store_id, "request_count": 0, "forecast_quantity": 0.0})
        entry["request_count"] += 1
        for forecast in REQUEST_REPOSITORY.list_forecasts(request.request_id):
            entry["forecast_quantity"] += forecast.forecast_quantity
    dashboard.update({
        "pending_approvals": pending,
        "approved_purchase_value": round(approved_value, 2),
        "modified_recommendations": modified,
        "regional_demand_trends": list(regional.values()),
    })
    return dashboard


@router.get("/alerts")
def alerts(identity: IdentityContext = Depends(require_roles(UserRole.EMPLOYEE, UserRole.ADMIN))) -> dict:
    return {"alerts": [item.model_dump(mode="json") for item in ALERT_REPOSITORY.list()]}


@router.get("/analytics")
def analytics(
    region: str | None = None, store: str | None = None,
    identity: IdentityContext = Depends(require_roles(UserRole.EMPLOYEE, UserRole.ADMIN)),
) -> dict:
    return _analytics_payload(region=region, store=store)

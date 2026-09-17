from __future__ import annotations

from enum import Enum
from datetime import datetime, date
from typing import Any, Literal

from pydantic import BaseModel, Field


class Product(BaseModel):
    id: str
    name: str
    category: str
    current_inventory: int = Field(ge=0)
    supplier_lead_time_days: int = Field(ge=1)
    minimum_order_quantity: int = Field(ge=1)
    unit_cost: float = Field(gt=0)


class Region(BaseModel):
    region_id: str = ""
    country: str = Field(min_length=1)
    state: str = Field(min_length=1)
    city: str = Field(min_length=1)
    region: str = Field(min_length=1)
    store_id: str = Field(min_length=1)


class Store(BaseModel):
    store_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    region: str = Field(min_length=1)
    city: str = ""
    state: str = ""
    country: str = ""
    region_id: str = ""
    location: str = ""
    active: bool = True


class InventoryItem(BaseModel):
    product_id: str = Field(min_length=1)
    product_name: str = Field(min_length=1)
    current_stock: int = Field(ge=0)
    unit_cost: float = Field(gt=0)
    supplier_lead_time_days: int = Field(ge=1)
    minimum_order_quantity: int = Field(ge=1)


class HistoricalSalesUpload(BaseModel):
    file_name: str = Field(min_length=1)
    s3_key: str | None = None
    content_type: str | None = None
    row_count: int = Field(ge=0, default=0)


class RequestStatus(str, Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    ANALYZING = "ANALYZING"
    AI_RECOMMENDED = "AI_RECOMMENDED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    MODIFIED = "MODIFIED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class UserRole(str, Enum):
    CUSTOMER = "CUSTOMER"
    EMPLOYEE = "EMPLOYEE"
    ADMIN = "ADMIN"


class User(BaseModel):
    user_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    email: str = Field(min_length=3)
    role: UserRole
    region: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Inventory(BaseModel):
    store_id: str = Field(min_length=1)
    product_id: str = Field(min_length=1)
    current_quantity: int = Field(ge=0)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Sale(BaseModel):
    sales_id: str = Field(min_length=1)
    store_id: str = Field(min_length=1)
    region_id: str = Field(min_length=1)
    product_id: str = Field(min_length=1)
    date: date
    quantity: int = Field(ge=0)


class Forecast(BaseModel):
    forecast_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    product_id: str = Field(min_length=1)
    forecast_horizon: int = Field(ge=1)
    forecast_quantity: float = Field(ge=0)
    trend: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    calculation: dict[str, Any] = Field(default_factory=dict)


class InventoryRequest(BaseModel):
    request_id: str = Field(min_length=1)
    created_by: str = Field(min_length=1)
    created_by_role: UserRole
    region: Region
    forecast_horizon_days: int = Field(ge=1, default=7)
    inventory: list[InventoryItem] = Field(default_factory=list)
    historical_sales_source: str = Field(default="S3")
    historical_sales_upload: HistoricalSalesUpload | None = None
    constraints: dict[str, Any] = Field(default_factory=dict)
    status: str = Field(default=RequestStatus.DRAFT)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Recommendation(BaseModel):
    recommendation_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    product_id: str = Field(min_length=1)
    ai_quantity: int = Field(ge=0)
    manager_quantity: int | None = Field(default=None, ge=0)
    modified: bool = False
    modification_reason: str | None = None
    ai_status: str = Field(min_length=1)
    ai_priority: str = Field(min_length=1)
    ai_reason: str = Field(min_length=1)
    ai_risks: list[str] = Field(default_factory=list)
    ai_confidence: float = Field(ge=0, le=1)
    calculation_snapshot: dict[str, Any] = Field(default_factory=dict)
    final_status: str | None = None
    final_priority: str | None = None
    approval_status: str = Field(default=RequestStatus.REVIEW_REQUIRED)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    manager_priority: str | None = None
    manager_decision: str | None = None
    manager_comment: str | None = None
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None


class InventoryAlert(BaseModel):
    alert_id: str = Field(min_length=1)
    store_id: str = Field(min_length=1)
    region_id: str = Field(min_length=1)
    product_id: str = Field(min_length=1)
    status: Literal["WATCH", "REORDER", "URGENT", "OVERSTOCK"]
    priority: Literal["LOW", "MEDIUM", "HIGH"]
    current_inventory: int = Field(ge=0)
    recommended_order: int = Field(ge=0)
    reason: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AuditEvent(BaseModel):
    event_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    user_role: UserRole
    action: str = Field(min_length=1)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SalesPoint(BaseModel):
    date: date
    units: int = Field(ge=0)


class ForecastResult(BaseModel):
    product_id: str
    forecast_horizon: int = 7
    forecast_quantity: float = 0.0
    history_days: int
    trend: float
    seasonality: str
    confidence: float
    daily_forecast: list[float]
    forecast_7_day: float
    explanation: str


class ForecastSeries(BaseModel):
    product_id: str
    store_id: str
    region: Region
    forecast_7_day: float
    forecast_14_day: float
    trend: str
    confidence: float
    explanation: str = ""


class InventoryResult(BaseModel):
    product_id: str
    demand_variability: float = 0.0
    overstock_quantity: int = 0
    stockout_risk: bool = False
    overstock_risk: bool = False
    average_daily_demand: float
    demand_during_lead_time: float
    safety_stock: int
    reorder_point: int
    recommended_order_quantity: int
    days_until_stockout: float
    target_stock: int


class RiskResult(BaseModel):
    product_id: str
    status: Literal["NORMAL", "WATCH", "REORDER", "URGENT", "OVERSTOCK"]
    priority: Literal["LOW", "MEDIUM", "HIGH"]
    risks: list[str] = Field(default_factory=list)


class DecisionResult(BaseModel):
    product_id: str
    status: Literal["NORMAL", "WATCH", "REORDER", "URGENT", "OVERSTOCK"]
    priority: Literal["LOW", "MEDIUM", "HIGH"]
    recommended_order: int
    reason: str
    risks: list[str]
    confidence: float


class DecisionAgentResponse(BaseModel):
    status: Literal["NORMAL", "WATCH", "REORDER", "URGENT", "OVERSTOCK"]
    priority: Literal["LOW", "MEDIUM", "HIGH"]
    recommended_quantity: int = Field(ge=0)
    reason: str = Field(min_length=1)
    risks: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)


class ProductSummary(BaseModel):
    product: Product
    current_inventory: int
    forecast_7_day: float
    days_until_stockout: float
    risk: str
    recommended_order: int
    priority: str


class AnalysisResponse(BaseModel):
    product: Product
    history: list[SalesPoint]
    forecast: ForecastResult
    inventory: InventoryResult
    decision: DecisionResult
    explanation: str


class DashboardResponse(BaseModel):
    total_products: int
    stockout_risk: int
    reorder_required: int
    overstock: int
    total_recommended_purchase_value: float
    products: list[ProductSummary]

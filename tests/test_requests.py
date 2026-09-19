from __future__ import annotations

from app.core.models import InventoryItem, InventoryRequest, Region, RequestStatus, UserRole
from app.core.requests import REQUEST_REPOSITORY


def test_request_repository_creates_and_tracks_audit():
    request = InventoryRequest(
        request_id="REQ-001",
        created_by="cust-1",
        created_by_role=UserRole.CUSTOMER,
        region=Region(country="India", state="Karnataka", city="Bangalore", region="South India", store_id="BLR-042"),
        forecast_horizon_days=7,
        inventory=[
            InventoryItem(
                product_id="P001",
                product_name="Milk",
                current_stock=32,
                unit_cost=40,
                supplier_lead_time_days=2,
                minimum_order_quantity=10,
            )
        ],
    )

    created = REQUEST_REPOSITORY.create_request(request)
    assert created.status == RequestStatus.DRAFT

    submitted = REQUEST_REPOSITORY.submit_request(created.request_id, user_id="cust-1", user_role=UserRole.CUSTOMER)
    assert submitted.status == RequestStatus.SUBMITTED

    events = REQUEST_REPOSITORY.list_audit_events(created.request_id)
    assert [event.action for event in events] == ["REQUEST_CREATED", "REQUEST_SUBMITTED"]


def test_request_repository_filters_by_region_and_store():
    request = InventoryRequest(
        request_id="REQ-002",
        created_by="cust-2",
        created_by_role=UserRole.CUSTOMER,
        region=Region(country="India", state="Karnataka", city="Bangalore", region="South India", store_id="BLR-042"),
        forecast_horizon_days=14,
        inventory=[],
    )
    REQUEST_REPOSITORY.create_request(request)

    requests = REQUEST_REPOSITORY.list_requests(region="South India", store_id="BLR-042")
    assert any(item.request_id == "REQ-002" for item in requests)
    assert all(item.region.region == "South India" for item in requests)
    assert all(item.region.store_id == "BLR-042" for item in requests)

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from uuid import uuid4

from .models import AuditEvent, Forecast, InventoryRequest, Recommendation, RequestStatus, UserRole
from ..aws.storage import RequestStore


class RequestRepository:
    def __init__(self) -> None:
        self._requests: dict[str, InventoryRequest] = {}
        self._recommendations: dict[str, list[Recommendation]] = defaultdict(list)
        self._audit_events: dict[str, list[AuditEvent]] = defaultdict(list)
        self._forecasts: dict[str, list[Forecast]] = defaultdict(list)
        self._sales: list = []
        self._store = RequestStore()

    def create_request(self, request: InventoryRequest) -> InventoryRequest:
        request.status = RequestStatus.DRAFT
        request.created_at = datetime.utcnow()
        request.updated_at = request.created_at
        self._requests[request.request_id] = request
        self._persist_request(request)
        self.record_event(
            AuditEvent(
                event_id=str(uuid4()),
                request_id=request.request_id,
                user_id=request.created_by,
                user_role=request.created_by_role,
                action="REQUEST_CREATED",
                metadata={"status": request.status, "store_id": request.region.store_id},
            )
        )
        return request

    def save_sale(self, sale) -> None:
        self._sales.append(sale)

    def list_sales(self, *, region_id: str, store_id: str, product_id: str) -> list:
        return [item for item in self._sales if item.region_id == region_id and item.store_id == store_id and item.product_id == product_id]

    def save_forecast(self, forecast: Forecast) -> Forecast:
        self._forecasts[forecast.request_id].append(forecast)
        self._store.save_forecast(forecast.model_dump(mode="json"))
        return forecast

    def list_forecasts(self, request_id: str) -> list[Forecast]:
        values = self._forecasts.get(request_id, []).copy()
        if not values: values = [Forecast.model_validate(self._store.delete_keys(item)) for item in self._store.list_forecasts(request_id)]
        return values

    def save_recommendation(self, recommendation: Recommendation, user_id: str, user_role: UserRole) -> Recommendation:
        self._recommendations[recommendation.request_id].append(recommendation)
        self._store.save_recommendation(recommendation.model_dump(mode="json"))
        self.record_event(
            AuditEvent(
                event_id=str(uuid4()),
                request_id=recommendation.request_id,
                user_id=user_id,
                user_role=user_role,
                action="AI_RECOMMENDATION_GENERATED",
                metadata={
                    "product_id": recommendation.product_id,
                    "ai_quantity": recommendation.ai_quantity,
                    "status": recommendation.approval_status,
                },
            )
        )
        return recommendation

    def get_recommendation(self, recommendation_id: str) -> Recommendation:
        for recommendation_list in self._recommendations.values():
            for recommendation in recommendation_list:
                if recommendation.recommendation_id == recommendation_id:
                    return recommendation
        for item in self._store.list_requests():
            for rec in self._store.list_recommendations(item["request_id"]):
                if rec.get("recommendation_id") == recommendation_id:
                    return Recommendation.model_validate(self._store.delete_keys(rec))
        raise KeyError(recommendation_id)

    def _update_request_status(self, request_id: str, status: RequestStatus) -> InventoryRequest:
        request = self.get_request(request_id)
        request.status = status
        request.updated_at = datetime.utcnow()
        self._persist_request(request)
        return request

    def submit_request(self, request_id: str, user_id: str, user_role: UserRole) -> InventoryRequest:
        request = self._update_request_status(request_id, RequestStatus.SUBMITTED)
        self.record_event(
            AuditEvent(
                event_id=str(uuid4()),
                request_id=request_id,
                user_id=user_id,
                user_role=user_role,
                action="REQUEST_SUBMITTED",
                metadata={"status": request.status},
            )
        )
        return request

    def mark_request_analyzing(self, request_id: str, user_id: str, user_role: UserRole) -> InventoryRequest:
        request = self._update_request_status(request_id, RequestStatus.ANALYZING)
        self.record_event(
            AuditEvent(
                event_id=str(uuid4()),
                request_id=request_id,
                user_id=user_id,
                user_role=user_role,
                action="REQUEST_ANALYZING",
                metadata={"status": request.status},
            )
        )
        return request

    def mark_request_review_required(self, request_id: str, user_id: str, user_role: UserRole) -> InventoryRequest:
        request = self._update_request_status(request_id, RequestStatus.REVIEW_REQUIRED)
        self.record_event(
            AuditEvent(
                event_id=str(uuid4()),
                request_id=request_id,
                user_id=user_id,
                user_role=user_role,
                action="REQUEST_REVIEW_REQUIRED",
                metadata={"status": request.status},
            )
        )
        return request

    def modify_recommendation(
        self,
        recommendation_id: str,
        *,
        manager_quantity: int | None,
        final_status: str | None,
        final_priority: str | None,
        reason: str | None,
        user_id: str,
        user_role: UserRole,
    ) -> Recommendation:
        recommendation = self.get_recommendation(recommendation_id)
        request = self.get_request(recommendation.request_id)
        if request.status not in {RequestStatus.REVIEW_REQUIRED, RequestStatus.MODIFIED}:
            raise ValueError("recommendation is not available for modification")
        if manager_quantity is None and final_priority is None and not reason:
            raise ValueError("at least one manager modification is required")
        recommendation.manager_quantity = manager_quantity
        recommendation.manager_priority = final_priority
        recommendation.manager_comment = reason
        recommendation.modified = True
        recommendation.modification_reason = reason
        recommendation.final_status = final_status
        recommendation.final_priority = final_priority
        recommendation.approval_status = RequestStatus.MODIFIED
        recommendation.updated_at = datetime.utcnow()
        self._update_request_status(recommendation.request_id, RequestStatus.MODIFIED)
        self.record_event(
            AuditEvent(
                event_id=str(uuid4()),
                request_id=recommendation.request_id,
                user_id=user_id,
                user_role=user_role,
                action="RECOMMENDATION_MODIFIED",
                metadata={
                    "recommendation_id": recommendation_id,
                    "manager_quantity": manager_quantity,
                    "final_status": final_status,
                    "final_priority": final_priority,
                    "reason": reason,
                },
            )
        )
        self._store.save_recommendation(recommendation.model_dump(mode="json"))
        return recommendation

    def approve_recommendation(self, recommendation_id: str, user_id: str, user_role: UserRole) -> Recommendation:
        recommendation = self.get_recommendation(recommendation_id)
        request = self.get_request(recommendation.request_id)
        if request.status not in {RequestStatus.REVIEW_REQUIRED, RequestStatus.MODIFIED}:
            raise ValueError("recommendation is not awaiting approval")
        recommendation.approval_status = RequestStatus.APPROVED
        recommendation.final_status = recommendation.final_status or recommendation.ai_status
        recommendation.final_priority = recommendation.manager_priority or recommendation.final_priority or recommendation.ai_priority
        recommendation.manager_decision = "APPROVED"
        recommendation.reviewed_by = user_id
        recommendation.reviewed_at = datetime.utcnow()
        recommendation.updated_at = datetime.utcnow()
        self._update_request_status(recommendation.request_id, RequestStatus.APPROVED)
        self.record_event(
            AuditEvent(
                event_id=str(uuid4()),
                request_id=recommendation.request_id,
                user_id=user_id,
                user_role=user_role,
                action="RECOMMENDATION_APPROVED",
                metadata={
                    "recommendation_id": recommendation_id,
                    "ai_quantity": recommendation.ai_quantity,
                    "manager_quantity": recommendation.manager_quantity,
                    "final_quantity": recommendation.manager_quantity if recommendation.manager_quantity is not None else recommendation.ai_quantity,
                    "status": recommendation.approval_status,
                },
            )
        )
        self._store.save_recommendation(recommendation.model_dump(mode="json"))
        return recommendation

    def reject_recommendation(self, recommendation_id: str, *, reason: str, user_id: str, user_role: UserRole) -> Recommendation:
        recommendation = self.get_recommendation(recommendation_id)
        request = self.get_request(recommendation.request_id)
        if request.status not in {RequestStatus.REVIEW_REQUIRED, RequestStatus.MODIFIED}:
            raise ValueError("recommendation is not awaiting rejection")
        recommendation.approval_status = RequestStatus.REJECTED
        recommendation.manager_decision = "REJECTED"
        recommendation.manager_comment = reason
        recommendation.reviewed_by = user_id
        recommendation.reviewed_at = datetime.utcnow()
        recommendation.updated_at = datetime.utcnow()
        self._update_request_status(recommendation.request_id, RequestStatus.REJECTED)
        self.record_event(
            AuditEvent(
                event_id=str(uuid4()),
                request_id=recommendation.request_id,
                user_id=user_id,
                user_role=user_role,
                action="RECOMMENDATION_REJECTED",
                metadata={"recommendation_id": recommendation_id, "status": recommendation.approval_status, "ai_quantity": recommendation.ai_quantity, "manager_comment": reason},
            )
        )
        self._store.save_recommendation(recommendation.model_dump(mode="json"))
        return recommendation

    def list_requests(self, created_by: str | None = None, region: str | None = None, store_id: str | None = None, status: str | None = None, priority: str | None = None) -> list[InventoryRequest]:
        values = list(self._requests.values())
        if not values:
            values = [self._hydrate_request(item) for item in self._store.list_requests()]
        if created_by:
            values = [item for item in values if item.created_by == created_by]
        if region:
            values = [item for item in values if item.region.region == region]
        if store_id:
            values = [item for item in values if item.region.store_id == store_id]
        if status:
            values = [item for item in values if item.status == status]
        if priority:
            request_ids = {rec.request_id for recs in self._recommendations.values() for rec in recs if (rec.final_priority or rec.manager_priority or rec.ai_priority) == priority}
            values = [item for item in values if item.request_id in request_ids]
        return sorted(values, key=lambda item: item.updated_at, reverse=True)

    def _persist_request(self, request: InventoryRequest) -> None:
        self._store.save_request(request.model_dump(mode="json"))

    def _hydrate_request(self, item: dict) -> InventoryRequest:
        return InventoryRequest.model_validate(self._store.delete_keys(item))

    def get_request(self, request_id: str) -> InventoryRequest:
        if request_id in self._requests:
            return self._requests[request_id]
        item = self._store.get_request(request_id)
        if not item:
            raise KeyError(request_id)
        request = self._hydrate_request(item)
        self._requests[request_id] = request
        return request

    def list_recommendations(self, request_id: str) -> list[Recommendation]:
        values = self._recommendations.get(request_id, []).copy()
        if not values: values = [Recommendation.model_validate(self._store.delete_keys(item)) for item in self._store.list_recommendations(request_id)]
        return values

    def list_all_recommendations(self) -> list[Recommendation]:
        values = [item for items in self._recommendations.values() for item in items]
        if values:
            return values
        return [Recommendation.model_validate(self._store.delete_keys(item)) for item in self._store.list_all_recommendations()]

    def record_event(self, event: AuditEvent) -> AuditEvent:
        self._audit_events[event.request_id].append(event)
        self._store.save_event(event.model_dump(mode="json"))
        return event

    def list_audit_events(self, request_id: str) -> list[AuditEvent]:
        values = self._audit_events.get(request_id, []).copy()
        if not values:
            values = [AuditEvent.model_validate(self._store.delete_keys(item)) for item in self._store.list_events(request_id)]
        return sorted(values, key=lambda event: (event.timestamp, event.event_id))


REQUEST_REPOSITORY = RequestRepository()

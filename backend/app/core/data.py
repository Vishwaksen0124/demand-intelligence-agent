from __future__ import annotations

from datetime import datetime
from .models import AuditEvent, Forecast, Inventory, Product, Recommendation, Region, Sale, Store, User


class DataRepository:
    """Validated local repository with access patterns matching the DynamoDB design."""
    def __init__(self):
        self.users, self.regions, self.stores, self.products = {}, {}, {}, {}
        self.inventory, self.sales, self.requests = {}, {}, {}
        self.forecasts, self.recommendations, self.audit_events = {}, {}, {}

    def put_user(self, item: User): self.users[item.user_id] = item; return item
    def put_region(self, item: Region):
        self.regions[item.region] = item
        if getattr(item, "region_id", ""): self.regions[item.region_id] = item
        return item
    def put_store(self, item: Store):
        if item.region not in self.regions: raise ValueError("store references an unknown region")
        self.stores[item.store_id] = item; return item
    def put_product(self, item: Product): self.products[item.id] = item; return item
    def put_inventory(self, item: Inventory):
        if item.store_id not in self.stores: raise ValueError("inventory references an unknown store")
        if item.product_id not in self.products: raise ValueError("inventory references an unknown product")
        item.updated_at = datetime.utcnow(); self.inventory[(item.store_id, item.product_id)] = item; return item
    def get_inventory(self, store_id, product_id): return self.inventory[(store_id, product_id)]
    def list_inventory(self, store_id=None, product_id=None):
        return [x for x in self.inventory.values() if (not store_id or x.store_id == store_id) and (not product_id or x.product_id == product_id)]
    def put_sale(self, item: Sale): self.sales[item.sales_id] = item; return item
    def list_sales(self, store_id=None, region_id=None, product_id=None):
        return sorted([x for x in self.sales.values() if (not store_id or x.store_id == store_id) and (not region_id or x.region_id == region_id) and (not product_id or x.product_id == product_id)], key=lambda x: x.date)
    def put_request(self, item): self.requests[item.request_id] = item; return item
    def get_request(self, request_id): return self.requests[request_id]
    def put_forecast(self, item: Forecast):
        if item.request_id not in self.requests: raise ValueError("forecast references an unknown request")
        self.forecasts[item.forecast_id] = item; return item
    def get_forecasts(self, request_id): return [x for x in self.forecasts.values() if x.request_id == request_id]
    def put_recommendation(self, item: Recommendation):
        if item.request_id not in self.requests: raise ValueError("recommendation references an unknown request")
        self.recommendations[item.recommendation_id] = item; return item
    def get_recommendations(self, request_id): return [x for x in self.recommendations.values() if x.request_id == request_id]
    def put_audit_event(self, item: AuditEvent): self.audit_events[item.event_id] = item; return item
    def get_audit_events(self, request_id): return sorted([x for x in self.audit_events.values() if x.request_id == request_id], key=lambda x: x.timestamp)

from __future__ import annotations

from .models import Region, Store


REGIONS = [
    Region(country="India", state="Karnataka", city="Bangalore", region="South India", store_id="BLR-042"),
    Region(country="India", state="Telangana", city="Hyderabad", region="South India", store_id="HYD-017"),
    Region(country="India", state="Tamil Nadu", city="Chennai", region="South India", store_id="CHE-009"),
    Region(country="India", state="Maharashtra", city="Mumbai", region="West India", store_id="MUM-003"),
    Region(country="India", state="Delhi", city="Delhi", region="North India", store_id="DEL-011"),
]

STORES = [
    Store(store_id="BLR-042", name="Bangalore Central", region="South India", city="Bangalore", state="Karnataka", country="India"),
    Store(store_id="HYD-017", name="Hyderabad Hub", region="South India", city="Hyderabad", state="Telangana", country="India"),
    Store(store_id="CHE-009", name="Chennai East", region="South India", city="Chennai", state="Tamil Nadu", country="India"),
    Store(store_id="MUM-003", name="Mumbai Prime", region="West India", city="Mumbai", state="Maharashtra", country="India"),
    Store(store_id="DEL-011", name="Delhi North", region="North India", city="Delhi", state="Delhi", country="India"),
]


def list_regions() -> list[Region]:
    return REGIONS.copy()


def list_stores(region_name: str | None = None) -> list[Store]:
    if not region_name:
        return STORES.copy()
    return [store for store in STORES if store.region == region_name]


def get_store(store_id: str) -> Store:
    for store in STORES:
        if store.store_id == store_id:
            return store
    raise KeyError(store_id)

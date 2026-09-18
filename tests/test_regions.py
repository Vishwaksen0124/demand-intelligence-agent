from __future__ import annotations

from app.core.regions import get_store, list_regions, list_stores


def test_regions_include_multiple_business_locations():
    regions = list_regions()
    stores = list_stores()

    assert len(regions) >= 5
    assert len(stores) >= 5
    assert get_store("BLR-042").city == "Bangalore"

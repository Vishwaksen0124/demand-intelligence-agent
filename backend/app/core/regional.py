from __future__ import annotations

from .models import Sale, SalesPoint


def filter_sales(sales: list[Sale], *, region_id: str, store_id: str, product_id: str) -> list[Sale]:
    """Return only sales belonging to the exact request scope."""
    return sorted([item for item in sales if item.region_id == region_id and item.store_id == store_id and item.product_id == product_id], key=lambda item: item.date)


def sales_to_history(sales: list[Sale]) -> list[SalesPoint]:
    return [SalesPoint(date=item.date, units=item.quantity) for item in sales]

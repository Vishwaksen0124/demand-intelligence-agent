from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .models import Product, SalesPoint


DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "synthetic_dataset.json"


@lru_cache(maxsize=1)
def load_catalog() -> dict:
    with DATA_FILE.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def list_products() -> list[Product]:
    return [Product.model_validate(item) for item in load_catalog()["products"]]


def get_product(product_id: str) -> Product:
    for item in list_products():
        if item.id == product_id:
            return item
    raise KeyError(product_id)


def get_history(product_id: str) -> list[SalesPoint]:
    history = load_catalog()["sales_history"][product_id]
    return [SalesPoint.model_validate(item) for item in history]

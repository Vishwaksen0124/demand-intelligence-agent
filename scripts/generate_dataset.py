from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "synthetic_dataset.json"


def product_blueprints():
    return [
        ("P001", "Atlas Notebook", "Office", 84, 7, 20, 12.5, "stable"),
        ("P002", "Pulse Bottle", "Lifestyle", 140, 5, 24, 8.0, "increasing"),
        ("P003", "Nova Cable", "Electronics", 160, 6, 30, 6.5, "stable"),
        ("P004", "Summit Lamp", "Home", 65, 8, 15, 27.0, "seasonal"),
        ("P005", "Echo Speaker", "Electronics", 52, 4, 12, 49.0, "spiky"),
        ("P006", "Harbor Mug", "Lifestyle", 175, 6, 24, 11.0, "stable"),
        ("P007", "Orbit Pen", "Office", 240, 4, 50, 2.4, "increasing"),
        ("P008", "Vivid Planner", "Office", 92, 7, 18, 16.0, "seasonal"),
        ("P009", "Terra Chair", "Home", 28, 10, 6, 89.0, "decreasing"),
        ("P010", "Prism Stand", "Electronics", 110, 5, 20, 18.0, "stable"),
        ("P011", "Anchor Tote", "Lifestyle", 74, 9, 16, 21.0, "increasing"),
        ("P012", "Drift Keyboard", "Electronics", 36, 6, 8, 74.0, "spiky"),
        ("P013", "Harbor Lamp", "Home", 94, 8, 18, 31.0, "seasonal"),
        ("P014", "Zen Journal", "Office", 180, 4, 24, 9.0, "stable"),
        ("P015", "Comet Charger", "Electronics", 63, 5, 12, 19.5, "increasing"),
        ("P016", "Ridge Backpack", "Lifestyle", 47, 7, 10, 58.0, "decreasing"),
        ("P017", "Mosaic Frame", "Home", 132, 9, 20, 14.0, "stable"),
        ("P018", "Vector Mouse", "Electronics", 89, 5, 14, 23.0, "spiky"),
        ("P019", "Nimbus Candle", "Home", 120, 6, 18, 13.5, "seasonal"),
        ("P020", "Lumen Flask", "Lifestyle", 101, 4, 15, 17.5, "increasing"),
    ]


def units_for(day_index: int, profile: str, base: float) -> int:
    if profile == "stable":
        value = base + ((day_index % 5) - 2) * 0.7
    elif profile == "increasing":
        value = base + day_index * 0.18 + ((day_index % 4) - 1.5) * 0.8
    elif profile == "decreasing":
        value = max(1.0, base - day_index * 0.16 + ((day_index % 3) - 1) * 0.6)
    elif profile == "seasonal":
        value = base + (4 if day_index % 14 < 7 else -1) + ((day_index % 6) - 2.5) * 0.6
    else:
        value = base + (7 if day_index in {11, 28, 55, 73} else 0) + ((day_index % 6) - 2.5) * 0.9
    return max(0, int(round(value)))


def build_dataset():
    start = date.today() - timedelta(days=89)
    products = []
    sales_history = {}

    for index, (product_id, name, category, inventory, lead_time, min_order, cost, profile) in enumerate(product_blueprints()):
        products.append(
            {
                "id": product_id,
                "name": name,
                "category": category,
                "current_inventory": inventory,
                "supplier_lead_time_days": lead_time,
                "minimum_order_quantity": min_order,
                "unit_cost": cost,
            }
        )
        base = 10 + (index % 5) * 2.5
        sales_history[product_id] = [
            {"date": str(start + timedelta(days=offset)), "units": units_for(offset, profile, base)}
            for offset in range(90)
        ]

    return {"generated_at": str(date.today()), "products": products, "sales_history": sales_history}


if __name__ == "__main__":
    OUTPUT.write_text(json.dumps(build_dataset(), indent=2), encoding="utf-8")
    print(f"Wrote {OUTPUT}")

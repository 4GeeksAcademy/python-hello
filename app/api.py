"""FastAPI inventory backend for Carla's Bakery Supplies."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

DATA_PATH = Path(__file__).resolve().parent.parent / "data.json"
LOW_STOCK_THRESHOLD = 10

app = FastAPI(title="Carla Bakery Inventory API")


class StockChange(BaseModel):
    name: str = Field(..., min_length=1)
    quantity: float = Field(..., gt=0)
    unit: str | None = Field(default=None, description="Required when creating a new product on receive")


def _load_data() -> dict[str, Any]:
    if not DATA_PATH.exists():
        return {"products": []}
    with DATA_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def _save_data(data: dict[str, Any]) -> None:
    with DATA_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def _find_product(products: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    key = name.strip().lower()
    for product in products:
        if product["name"].strip().lower() == key:
            return product
    return None


@app.get("/products")
def list_products() -> dict[str, Any]:
    data = _load_data()
    return {"products": data.get("products", [])}


@app.get("/products/low-stock")
def low_stock() -> dict[str, Any]:
    data = _load_data()
    items = [
        p
        for p in data.get("products", [])
        if float(p.get("quantity", 0)) <= LOW_STOCK_THRESHOLD
    ]
    return {"threshold": LOW_STOCK_THRESHOLD, "products": items}


@app.post("/products/receive")
def receive_stock(body: StockChange) -> dict[str, Any]:
    data = _load_data()
    products = data.setdefault("products", [])
    product = _find_product(products, body.name)

    if product is None:
        if not body.unit:
            raise HTTPException(
                status_code=400,
                detail="unit is required when registering a new product",
            )
        product = {
            "name": body.name.strip(),
            "quantity": float(body.quantity),
            "unit": body.unit.strip(),
        }
        products.append(product)
    else:
        product["quantity"] = float(product["quantity"]) + float(body.quantity)
        if body.unit:
            product["unit"] = body.unit.strip()

    _save_data(data)
    return {"message": "stock received", "product": product}


@app.post("/products/sell")
def sell_stock(body: StockChange) -> dict[str, Any]:
    data = _load_data()
    products = data.setdefault("products", [])
    product = _find_product(products, body.name)

    if product is None:
        raise HTTPException(status_code=404, detail=f"product not found: {body.name}")

    current = float(product["quantity"])
    qty = float(body.quantity)
    if qty > current:
        raise HTTPException(
            status_code=400,
            detail=f"insufficient stock: have {current}, requested {qty}",
        )

    product["quantity"] = current - qty
    _save_data(data)
    return {"message": "stock sold", "product": product}

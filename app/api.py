"""FastAPI inventory backend for Carla's Bakery Supplies."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

DATA_PATH = Path(__file__).resolve().parent.parent / "products.csv"
LOW_STOCK_THRESHOLD = 10
CSV_FIELDS = ("name", "quantity", "unit")

app = FastAPI(title="Carla Bakery Inventory API")


class StockChange(BaseModel):
    name: str = Field(..., min_length=1)
    quantity: float = Field(..., gt=0)
    unit: str | None = Field(
        default=None, description="Required when creating a new product on receive"
    )


def _load_products() -> list[dict[str, Any]]:
    if not DATA_PATH.exists():
        return []
    with DATA_PATH.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        products: list[dict[str, Any]] = []
        for row in reader:
            if not row.get("name"):
                continue
            products.append(
                {
                    "name": row["name"].strip(),
                    "quantity": float(row.get("quantity") or 0),
                    "unit": (row.get("unit") or "units").strip(),
                }
            )
        return products


def _save_products(products: list[dict[str, Any]]) -> None:
    with DATA_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(CSV_FIELDS))
        writer.writeheader()
        for product in products:
            writer.writerow(
                {
                    "name": product["name"],
                    "quantity": product["quantity"],
                    "unit": product["unit"],
                }
            )


def _find_product(products: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    key = name.strip().lower()
    for product in products:
        if product["name"].strip().lower() == key:
            return product
    return None


@app.get("/products")
def list_products() -> dict[str, Any]:
    return {"products": _load_products()}


@app.get("/products/low-stock")
def low_stock() -> dict[str, Any]:
    items = [
        p for p in _load_products() if float(p.get("quantity", 0)) <= LOW_STOCK_THRESHOLD
    ]
    return {"threshold": LOW_STOCK_THRESHOLD, "products": items}


@app.post("/products/receive")
def receive_stock(body: StockChange) -> dict[str, Any]:
    products = _load_products()
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

    _save_products(products)
    return {"message": "stock received", "product": product}


@app.post("/products/sell")
def sell_stock(body: StockChange) -> dict[str, Any]:
    products = _load_products()
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
    _save_products(products)
    return {"message": "stock sold", "product": product}

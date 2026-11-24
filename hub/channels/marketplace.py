"""Channel B: mock marketplace (JSON Server). Simple REST: /listings, /orders."""
import os

import httpx

BASE = os.getenv("MARKETPLACE_URL", "http://localhost:3001")


def create_listing(sku: str, title: str, description: str, price: float, stock: int) -> str:
    r = httpx.post(f"{BASE}/listings", json={
        "sku": sku, "title": title, "description": description,
        "price": price, "stock": stock})
    r.raise_for_status()
    return str(r.json()["id"])


def update_stock(external_id: str, stock: int) -> None:
    httpx.patch(f"{BASE}/listings/{external_id}", json={"stock": stock}).raise_for_status()


def fetch_orders() -> list[dict]:
    """Return orders as [{external_id, sku, qty, total, status}]."""
    r = httpx.get(f"{BASE}/orders")
    r.raise_for_status()
    return [{"external_id": str(o["id"]), "sku": o["sku"], "qty": o["qty"],
             "total": o.get("total"), "status": o.get("status", "pending")} for o in r.json()]


def update_order_status(external_id: str, status: str) -> None:
    httpx.patch(f"{BASE}/orders/{external_id}", json={"status": status}).raise_for_status()

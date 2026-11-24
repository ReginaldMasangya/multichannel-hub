"""Channel A: WooCommerce REST API (wc/v3). Needs WOO_CONSUMER_KEY/SECRET in .env."""
import os

import httpx

BASE = os.getenv("WOO_URL", "http://localhost:8080") + "/wp-json/wc/v3"


def _auth():
    return (os.environ["WOO_CONSUMER_KEY"], os.environ["WOO_CONSUMER_SECRET"])


def create_listing(sku: str, title: str, description: str, price: float, stock: int) -> str:
    r = httpx.post(f"{BASE}/products", auth=_auth(), json={
        "name": title, "sku": sku, "description": description,
        "regular_price": str(price), "manage_stock": True, "stock_quantity": stock})
    r.raise_for_status()
    return str(r.json()["id"])


def update_stock(external_id: str, stock: int) -> None:
    httpx.put(f"{BASE}/products/{external_id}", auth=_auth(),
              json={"stock_quantity": stock}).raise_for_status()


def fetch_orders() -> list[dict]:
    """Flatten Woo orders into one row per line item: [{external_id, sku, qty, total, status}]."""
    r = httpx.get(f"{BASE}/orders", auth=_auth(), params={"per_page": 50})
    r.raise_for_status()
    rows = []
    for o in r.json():
        for item in o["line_items"]:
            rows.append({"external_id": f'{o["id"]}-{item["id"]}', "sku": item["sku"],
                         "qty": item["quantity"], "total": item["total"],
                         "status": o["status"]})
    return rows


def update_order_status(external_id: str, status: str) -> None:
    order_id = external_id.split("-")[0]
    httpx.put(f"{BASE}/orders/{order_id}", auth=_auth(), json={"status": status}).raise_for_status()

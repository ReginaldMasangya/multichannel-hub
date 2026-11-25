"""Channel A: WooCommerce REST API (wc/v3). Needs WOO_CONSUMER_KEY/SECRET in .env."""
import os

import httpx

BASE = os.getenv("WOO_URL", "http://localhost:8080") + "/wp-json/wc/v3"

# Orders that must not take stock. "checkout-draft" is a checkout nobody finished.
DEAD_STATUSES = {"cancelled", "failed", "refunded", "trash", "checkout-draft"}


def _auth():
    return (os.environ["WOO_CONSUMER_KEY"], os.environ["WOO_CONSUMER_SECRET"])


def create_listing(sku: str, title: str, description: str, price: float, stock: int) -> str:
    r = httpx.post(f"{BASE}/products", auth=_auth(), json={
        "name": title, "sku": sku, "description": description,
        "regular_price": str(price), "manage_stock": True, "stock_quantity": stock})
    r.raise_for_status()
    return str(r.json()["id"])


def import_listings() -> list[dict]:
    """Fetch every product from Woo as [{external_id, sku, title, description, price, stock}]."""
    rows = []
    page = 1
    while True:
        r = httpx.get(f"{BASE}/products", auth=_auth(),
                      params={"per_page": 100, "page": page})
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        for p in batch:
            rows.append({"external_id": str(p["id"]), "sku": p.get("sku") or "",
                         "title": p.get("name") or "",
                         "description": p.get("description") or "",
                         "price": float(p.get("regular_price") or p.get("price") or 0),
                         "stock": int(p.get("stock_quantity") or 0)})
        if len(batch) < 100:
            break
        page += 1
    return rows


def update_stock(external_id: str, stock: int) -> None:
    httpx.put(f"{BASE}/products/{external_id}", auth=_auth(),
              json={"stock_quantity": stock}).raise_for_status()


def is_sale(status: str) -> bool:
    """Same rule as PrestaShop: unpaid orders reserve stock, dead orders don't."""
    return status not in DEAD_STATUSES


def fetch_orders() -> list[dict]:
    """Flatten Woo orders into one row per line item: [{external_id, sku, qty, total, status}]."""
    r = httpx.get(f"{BASE}/orders", auth=_auth(), params={"per_page": 50})
    r.raise_for_status()
    rows = []
    for o in r.json():
        if not is_sale(o["status"]):
            continue  # not saved in the hub, so it's picked up if it later revives
        for item in o["line_items"]:
            rows.append({"external_id": f'{o["id"]}-{item["id"]}', "sku": item["sku"],
                         "qty": item["quantity"], "total": item["total"],
                         "status": o["status"]})
    return rows


def update_order_status(external_id: str, status: str) -> None:
    order_id = external_id.split("-")[0]
    httpx.put(f"{BASE}/orders/{order_id}", auth=_auth(), json={"status": status}).raise_for_status()

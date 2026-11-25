"""Channel B: PrestaShop, standing in for the marketplace. Needs PRESTASHOP_API_KEY in .env.

Three PrestaShop quirks this file hides from the rest of the hub:
  - It answers in XML unless we ask for output_format=JSON, and writes must be XML.
  - The SKU is called "reference".
  - Stock is not stored on the product. It lives in the "stock_availables" resource.
"""
import os
import re
import xml.etree.ElementTree as ET

import httpx
from dotenv import load_dotenv

load_dotenv()

TIMEOUT = 5          # seconds. Short, so a slow channel can't stall a sync run
IMPORT_TIMEOUT = 30  # reading the whole catalog is slower and isn't part of a sync run

LANGUAGE_ID = 1      # English on a fresh install
HOME_CATEGORY_ID = 2

# PrestaShop installs sample products ("demo_1", ...) and sample orders for them.
SAMPLE_PREFIX = "demo_"

# PrestaShop's default order state IDs
CANCELED, REFUNDED, PAYMENT_ERROR = 6, 7, 8
SHIPPED, DELIVERED = 4, 5
STATUS_TO_STATE = {"shipped": SHIPPED, "delivered": DELIVERED, "rejected": CANCELED}


def _request(method: str, path: str, *, params: dict | None = None,
             body: bytes | None = None, timeout: float = TIMEOUT) -> httpx.Response:
    # Env vars are read here, not at import time, so .env is always loaded first.
    base = os.getenv("PRESTASHOP_URL", "http://localhost:8081") + "/api"
    headers = {"Content-Type": "text/xml"} if body else {}
    # PrestaShop redirects any request not addressed to its own shop domain. Inside
    # Docker we connect to "prestashop", so we still have to name that domain.
    if os.getenv("PRESTASHOP_HOST"):
        headers["Host"] = os.environ["PRESTASHOP_HOST"]
    r = httpx.request(
        method, f"{base}/{path}",
        auth=(os.environ["PRESTASHOP_API_KEY"], ""),  # key is the username, no password
        params=params, content=body, timeout=timeout, headers=headers)
    r.raise_for_status()
    return r


def _get_list(resource: str, timeout: float = TIMEOUT, **params) -> list[dict]:
    data = _request("GET", resource, timeout=timeout,
                    params={"output_format": "JSON", **params}).json()
    # With no results, PrestaShop returns [] instead of {"products": [...]}
    return data.get(resource, []) if isinstance(data, dict) else []


def _text(value) -> str:
    """A translated field is a plain string, or [{id, value}] with several languages."""
    if isinstance(value, list):
        return value[0]["value"] if value else ""
    return value or ""


def _xml(node_name: str, fields: dict) -> ET.Element:
    root = ET.Element("prestashop")
    node = ET.SubElement(root, node_name)
    for key, value in fields.items():
        ET.SubElement(node, key).text = str(value)
    return root


def _add_translated(node: ET.Element, name: str, value: str) -> None:
    field = ET.SubElement(node, name)
    ET.SubElement(field, "language", id=str(LANGUAGE_ID)).text = value


def _clean_name(title: str) -> str:
    """PrestaShop rejects these characters in names, and names over 128 characters."""
    return re.sub(r"[<>;=#{}]", " ", title).strip()[:128]


def create_listing(sku: str, title: str, description: str, price: float, stock: int) -> str:
    name = _clean_name(title)
    root = _xml("product", {
        "reference": sku,
        "price": f"{price:.2f}",
        "id_category_default": HOME_CATEGORY_ID,
        "id_tax_rules_group": 0,   # no tax, so the shop price equals the hub price
        "state": 1,                # 1 = finished product (0 = hidden draft)
        "active": 1,
        "available_for_order": 1,
        "show_price": 1,
        "visibility": "both",
        "minimal_quantity": 1,
        "product_type": "standard",
    })
    product = root.find("product")
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "product"
    _add_translated(product, "name", name)
    _add_translated(product, "link_rewrite", slug)   # the product's URL slug
    _add_translated(product, "description", description)
    categories = ET.SubElement(ET.SubElement(product, "associations"), "categories")
    ET.SubElement(ET.SubElement(categories, "category"), "id").text = str(HOME_CATEGORY_ID)

    r = _request("POST", "products", body=ET.tostring(root))
    product_id = ET.fromstring(r.content).findtext("product/id")
    # PrestaShop ignores stock on the product itself, so set it separately.
    update_stock(product_id, stock)
    return product_id


def import_listings() -> list[dict]:
    """Fetch every listing as [{external_id, sku, title, description, price, stock}]."""
    products = _get_list("products", display="full", timeout=IMPORT_TIMEOUT)
    # id_product_attribute=0 is the product's total, not one size or colour
    stock_rows = _get_list("stock_availables", display="[id_product,quantity]",
                           timeout=IMPORT_TIMEOUT, **{"filter[id_product_attribute]": 0})
    stock = {str(row["id_product"]): int(row["quantity"]) for row in stock_rows}

    return [{"external_id": str(p["id"]), "sku": p["reference"],
             "title": _text(p.get("name")), "description": _text(p.get("description")),
             "price": float(p.get("price") or 0), "stock": stock.get(str(p["id"]), 0)}
            for p in products
            if p.get("reference") and not p["reference"].startswith(SAMPLE_PREFIX)]


def update_stock(external_id: str, stock: int) -> None:
    """Set the absolute stock number: find the stock row, change it, send it back."""
    found = _request("GET", "stock_availables", params={
        "filter[id_product]": external_id, "filter[id_product_attribute]": 0})
    link = ET.fromstring(found.content).find("stock_availables/stock_available")
    if link is None:
        # Raised as an HTTP 404 so sync.py's retry rules treat it as permanent
        raise httpx.HTTPStatusError(
            f"No stock record for PrestaShop product {external_id}",
            request=found.request, response=httpx.Response(404, request=found.request))

    stock_id = link.get("id")
    # A PUT replaces the whole record, so start from the current one
    root = ET.fromstring(_request("GET", f"stock_availables/{stock_id}").content)
    root.find("stock_available/quantity").text = str(stock)
    _request("PUT", f"stock_availables/{stock_id}", body=ET.tostring(root))


def is_sale(order_state: int) -> bool:
    """Should an order in this state take stock?

    Unpaid orders (such as "Awaiting bank wire payment") count, so the unit is
    reserved as soon as the buyer checks out. Dead orders don't.
    """
    return order_state not in {CANCELED, REFUNDED, PAYMENT_ERROR}


def _hub_status(order_state: int) -> str:
    return {SHIPPED: "shipped", DELIVERED: "delivered"}.get(order_state, "pending")


def fetch_orders() -> list[dict]:
    """One row per order line, newest 50 orders: [{external_id, sku, qty, total, status}]."""
    rows = []
    for order in _get_list("orders", display="full", sort="[id_DESC]", limit=50):
        state = int(order["current_state"])
        if not is_sale(state):
            continue
        for line in order.get("associations", {}).get("order_rows", []):
            sku = line["product_reference"]
            if sku.startswith(SAMPLE_PREFIX):
                continue
            qty = int(line["product_quantity"])
            rows.append({"external_id": f'{order["id"]}-{line["id"]}', "sku": sku,
                         "qty": qty,
                         "total": round(float(line["unit_price_tax_incl"]) * qty, 2),
                         "status": _hub_status(state)})
    return rows


def update_order_status(external_id: str, status: str) -> None:
    """Change an order's state by adding an entry to its history."""
    if status not in STATUS_TO_STATE:
        raise ValueError(f"No PrestaShop order state for status '{status}'")
    root = _xml("order_history", {"id_order": external_id.split("-")[0],
                                  "id_order_state": STATUS_TO_STATE[status]})
    _request("POST", "order_histories", body=ET.tostring(root))

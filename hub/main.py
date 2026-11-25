"""Hub API.  Run from the project folder:  uvicorn hub.main:app --reload"""
import io
from datetime import datetime

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse

from hub.db import ChannelListing, Order, Product, SessionLocal, StockEvent, engine, init_db
from hub.llm import adapt_listing
from hub.sync import CHANNELS, pull_orders, push_stock_everywhere
from pydantic import BaseModel

app = FastAPI(title="Multichannel Hub")
init_db()

class NewListing(BaseModel):
    sku: str
    name: str
    price: float
    stock: int
    description: str | None = None
    category: str | None = None

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/products")
def list_products():
    with SessionLocal() as s:
        return [{"sku": p.sku, "name": p.name, "category": p.category,
                 "price": float(p.price), "stock": p.stock} for p in s.query(Product)]


@app.post("/products/import")
def import_products():
    """Pull listings from every channel into the hub, matched by SKU, then push
    the hub's stock number back so every channel agrees.

    Only stock is merged: the lowest stock across channels (and any existing
    hub row) wins, so the hub never overstates availability. Existing hub
    name/price are left untouched; new products are created from channel data.
    """
    grouped: dict[str, dict] = {}
    errors = {}
    for name, client in CHANNELS.items():
        try:
            rows = client.import_listings()
        except Exception as e:  # one channel down shouldn't stop the other
            errors[name] = str(e)
            continue
        for row in rows:
            sku = row["sku"]
            if not sku:
                continue
            bucket = grouped.setdefault(sku, {"stock": row["stock"], "rows": []})
            bucket["stock"] = min(bucket["stock"], row["stock"])
            bucket["rows"].append((name, row))

    created = updated = linked = 0
    push_failed = []
    with SessionLocal() as s:
        for sku, bucket in grouped.items():
            product = s.query(Product).filter_by(sku=sku).first()
            if product is None:
                first = bucket["rows"][0][1]
                product = Product(sku=sku, name=first["title"] or sku,
                                  price=first["price"], stock=bucket["stock"],
                                  description=first["description"] or None)
                s.add(product)
                s.flush()
                created += 1
            elif bucket["stock"] < product.stock:
                product.stock = bucket["stock"]
                updated += 1

            for name, row in bucket["rows"]:
                listing = s.query(ChannelListing).filter_by(
                    product_id=product.id, channel=name).first()
                if listing is None:
                    s.add(ChannelListing(product_id=product.id, channel=name,
                                         external_id=row["external_id"],
                                         title=row["title"],
                                         last_synced_at=datetime.utcnow()))
                else:
                    listing.external_id = row["external_id"]
                    listing.title = row["title"]
                    listing.last_synced_at = datetime.utcnow()
                linked += 1

            # A failed push doesn't raise: it's recorded on the listing for retry.
            push_stock_everywhere(s, product)
            push_failed += [
                {"sku": sku, "channel": l.channel, "error": l.last_push_error}
                for l in s.query(ChannelListing).filter_by(
                    product_id=product.id, needs_push=True)]
        s.commit()

    result = {"skus": len(grouped), "created": created, "updated": updated,
              "listings": linked}
    if errors:
        result["errors"] = errors
    if push_failed:
        result["push_failed"] = push_failed
    return result


@app.post("/products/{sku}/publish")
def publish(sku: str):
    """Publish one product to every channel, with copy adapted per channel by Gemini."""
    with SessionLocal() as s:
        p = s.query(Product).filter_by(sku=sku).first()
        if not p:
            raise HTTPException(404, "Unknown SKU")
        results = {}
        for name, client in CHANNELS.items():
            if s.query(ChannelListing).filter_by(product_id=p.id, channel=name).first():
                results[name] = "already listed"
                continue
            copy = adapt_listing(p.name, p.description or "", name)
            ext_id = client.create_listing(p.sku, copy.title, copy.description,
                                           float(p.price), p.stock)
            s.add(ChannelListing(product_id=p.id, channel=name,
                                 external_id=ext_id, title=copy.title))
            results[name] = copy.title
        s.commit()
        return results


@app.post("/products")
def create_listing(listing: NewListing):
    with SessionLocal() as s:
        if s.query(Product).filter_by(sku=listing.sku).first():
            raise HTTPException(400, "SKU already exists")
        
        p = Product(sku=listing.sku, name=listing.name, price=listing.price, stock=listing.stock, description=listing.description, category=listing.category)

        s.add(p)
        s.commit()

        return {"sku": p.sku, "name": p.name}

@app.post("/sync/orders")
def sync_orders():
    with SessionLocal() as s:
        return pull_orders(s)


@app.get("/orders")
def list_orders():
    with SessionLocal() as s:
        return [{"channel": o.channel, "external_id": o.external_id, "sku": o.sku,
                 "qty": o.qty, "total": float(o.total or 0), "status": o.status,
                 "created_at": o.created_at.isoformat()} for o in s.query(Order)]


@app.get("/export")
def export(table: str = "orders", format: str = "csv"):
    """Download a table as CSV or XLSX."""
    allowed = {"orders", "products", "stock_events", "channel_listings"}
    if table not in allowed:
        raise HTTPException(400, f"table must be one of {sorted(allowed)}")
    df = pd.read_sql_table(table, engine)
    buf = io.BytesIO()
    if format == "xlsx":
        df.to_excel(buf, index=False)
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        df.to_csv(buf, index=False)
        media = "text/csv"
    buf.seek(0)
    return StreamingResponse(buf, media_type=media,
                             headers={"Content-Disposition": f"attachment; filename={table}.{format}"})

"""Seed data for the demo, in two independent modes.

    python -m hub.seed --channels   push products straight onto Woo + the marketplace
    python -m hub.seed --history    write ~50 past orders + stock movements into the hub

Run --channels first. It touches only Woo and the marketplace, not the hub —
the hub stays empty until tomorrow's Import feature pulls these listings in.
Only after Import has run does --history have products to write orders against.
"""
import argparse
import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

from hub.channels import marketplace, woocommerce
from hub.db import Order, Product, SessionLocal, StockEvent, init_db

CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "seed_products.csv"


def _load_catalog() -> list[dict]:
    with open(CSV_PATH, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _overlap_stock(woo_stock: int) -> int:
    """
    The ~10 SKUs seeded onto BOTH channels need a marketplace stock number
    that's deliberately different from what Woo got, so tomorrow's Import
    has a real conflict to resolve with the lower-stock-wins rule.
    """
    if woo_stock < 0:
        raise ValueError(f"The Woo stock must be non-negative value. Current Woo stock: {woo_stock}")
    
    if woo_stock == 0:
        return 0

    if woo_stock > 0:
        return woo_stock - random.randint(1, woo_stock)


def seed_channels() -> None:
    catalog = _load_catalog()
    woo_rows = catalog[:25]        # SKU-001..SKU-025
    market_rows = catalog[15:]     # SKU-016..SKU-036 -> 10 SKUs overlap with Woo
    woo_skus = {row["sku"] for row in woo_rows}

    for row in woo_rows:
        woocommerce.create_listing(row["sku"], row["name"], row["description"],
                                    float(row["price"]), int(row["stock"]))
    print(f"Pushed {len(woo_rows)} listings to WooCommerce")

    for row in market_rows:
        stock = int(row["stock"])
        if row["sku"] in woo_skus:
            stock = _overlap_stock(stock)
        marketplace.create_listing(row["sku"], row["name"], row["description"],
                                    float(row["price"]), stock)
    print(f"Pushed {len(market_rows)} listings to the marketplace (10 overlap with Woo)")


def seed_history(n_orders: int = 50, days: int = 30) -> None:
    init_db()
    with SessionLocal() as s:
        products = s.query(Product).all()
        if not products:
            print("No products in the hub yet. Run --channels, then use the "
                  "Products page's Import button, before --history.")
            return

        now = datetime.utcnow()
        for i in range(n_orders):
            product = random.choice(products)
            qty = random.randint(1, min(3, max(product.stock, 1)))
            channel = random.choice(["woocommerce", "marketplace"])
            placed_at = now - timedelta(days=random.uniform(0, days))

            s.add(Order(channel=channel, external_id=f"SEED-{i}", sku=product.sku,
                        qty=qty, total=product.price * qty, status="delivered",
                        created_at=placed_at))
            product.stock = max(product.stock - qty, 0)
            s.add(StockEvent(sku=product.sku, change=-qty, reason="sale",
                             channel=channel, created_at=placed_at))

        s.commit()
    print(f"Wrote {n_orders} past orders across {len(products)} products")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--channels", action="store_true", help="push products onto Woo + the marketplace")
    group.add_argument("--history", action="store_true", help="write past orders into the hub")
    args = parser.parse_args()

    seed_channels() if args.channels else seed_history()


if __name__ == "__main__":
    main()

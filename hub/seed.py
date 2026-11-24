"""Load data/seed_products.csv into the hub database.  Run: python -m hub.seed"""
import csv
from pathlib import Path

from hub.db import Product, SessionLocal, init_db

CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "seed_products.csv"


def main():
    init_db()
    with SessionLocal() as s, open(CSV_PATH, encoding="utf-8") as f:
        added = 0
        for row in csv.DictReader(f):
            if s.query(Product).filter_by(sku=row["sku"]).first():
                continue
            s.add(Product(sku=row["sku"], name=row["name"], category=row["category"],
                          price=row["price"], stock=int(row["stock"]),
                          description=row["description"]))
            added += 1
        s.commit()
    print(f"Seeded {added} products")


if __name__ == "__main__":
    main()

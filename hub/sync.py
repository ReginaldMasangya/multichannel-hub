"""Stock sync: the heart of the hub.

Flow when a sale happens on any channel:
  1. pull_orders() fetches new orders from every channel
  2. apply_sale() decides whether the sale is accepted and updates master stock  <-- YOU WRITE THIS
  3. push_stock_everywhere() sends the new stock number to every channel
"""
from datetime import datetime

from sqlalchemy.orm import Session

from hub.channels import marketplace, woocommerce
from hub.db import ChannelListing, Order, Product, StockEvent

CHANNELS = {"woocommerce": woocommerce, "marketplace": marketplace}


def apply_sale(session: Session, channel: str, sku: str, qty: int) -> bool:
    """Decide what happens when `channel` reports a sale of `qty` units of `sku`.

    Return True if the sale is accepted, False if rejected.

    Things to decide:
      - If qty > product.stock (the other channel already sold the last unit),
        do you reject the order, accept it as a backorder (stock goes negative),
        or accept only part of it?
      - Log every change as a StockEvent (change=-qty, reason="sale" or
        "rejected_oversell", channel=channel) so the dashboard can show it.
      - Hint: session.query(Product).filter_by(sku=sku).with_for_update().first()
        locks the row, so two syncs running at once can't both take the last unit.

    Don't commit here; pull_orders() commits once at the end.
    """
    # TODO(Reginald): implement your oversell policy (about 5-10 lines)
    raise NotImplementedError


def push_stock_everywhere(session: Session, product: Product) -> None:
    """Send the master stock number to every channel the product is listed on."""
    for listing in session.query(ChannelListing).filter_by(product_id=product.id):
        CHANNELS[listing.channel].update_stock(listing.external_id, max(product.stock, 0))
        listing.last_synced_at = datetime.utcnow()


def pull_orders(session: Session) -> dict:
    """Fetch orders from all channels, apply new ones, then sync stock. Safe to run repeatedly."""
    summary = {"new": 0, "accepted": 0, "rejected": 0}
    touched = set()
    for name, client in CHANNELS.items():
        try:
            orders = client.fetch_orders()
        except Exception as e:  # one channel down shouldn't stop the other
            summary[f"{name}_error"] = str(e)
            continue
        for o in orders:
            if session.query(Order).filter_by(channel=name, external_id=o["external_id"]).first():
                continue  # already processed: never count a sale twice
            ok = apply_sale(session, name, o["sku"], o["qty"])
            session.add(Order(channel=name, external_id=o["external_id"], sku=o["sku"],
                              qty=o["qty"], total=o["total"],
                              status="pending" if ok else "rejected"))
            summary["new"] += 1
            summary["accepted" if ok else "rejected"] += 1
            touched.add(o["sku"])
    for sku in touched:
        product = session.query(Product).filter_by(sku=sku).first()
        if product:
            push_stock_everywhere(session, product)
    session.commit()
    return summary

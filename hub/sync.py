"""Stock sync: the heart of the hub.

Flow when a sale happens on any channel:
  1. pull_orders() fetches new orders from every channel
  2. apply_sale() decides whether the sale is accepted and updates master stock
  3. push_stock_everywhere() sends the new stock number to every channel
"""
import httpx, logging

from datetime import datetime

from sqlalchemy.orm import Session

from hub.channels import marketplace, woocommerce
from hub.db import ChannelListing, Order, Product, StockEvent

CHANNELS = {"woocommerce": woocommerce, "marketplace": marketplace}

logger = logging.getLogger(__name__)

def apply_sale(session: Session, channel: str, sku: str, qty: int) -> bool:
    """Decide what happens when `channel` reports a sale of `qty` units of `sku`.

    Return True if the sale is accepted, False if rejected.

    Policy: reject oversells. The row is locked so concurrent syncs can't both
    take the last unit. A rejected sale logs a zero-change event for auditing.

    Don't commit here; pull_orders() commits once at the end.
    """
    product = session.query(Product).filter_by(sku=sku).with_for_update().first()
    if product is None:
        return False
    if qty > product.stock:
        session.add(StockEvent(sku=sku, change=0, reason="rejected_oversell", channel=channel))
        return False
    product.stock -= qty
    session.add(StockEvent(sku=sku, change=-qty, reason="sale", channel=channel))
    return True


def push_stock_everywhere(session: Session, product: Product) -> None:
    """Send the master stock number to every channel the product is listed on.

    A push to one channel failing must never crash this loop or skip the
    others — that's what needs_push/push_attempts/last_push_error exist for:
    record the failure on the listing and move on, instead of raising.
    """
    for listing in session.query(ChannelListing).filter_by(product_id=product.id):
        try:
            CHANNELS[listing.channel].update_stock(listing.external_id, max(product.stock, 0))
            listing.last_synced_at = datetime.utcnow()
            listing.needs_push = False
            listing.push_attempts = 0
            listing.last_push_error = None
        except httpx.TimeoutException as e:
            logger.warning(f"Timeout while pushing stock for {product.sku} to {listing.channel}: {e}")
            listing.needs_push = True
            listing.push_attempts += 1
            listing.last_push_error = str(e)
        
        except httpx.RequestError as e:
            logger.warning(f"Connection error while pushing stock for {product.sku} to {listing.channel}: {e}")
            listing.needs_push = True
            listing.push_attempts += 1
            listing.last_push_error = str(e)
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code

            if status_code == 429:
                logger.warning(f"Rate limit error while pushing stock for {product.sku} to {listing.channel}: {e}")
                listing.needs_push = True
                listing.push_attempts += 1
                listing.last_push_error = str(e)

            if status_code >= 500:
                logger.warning(f"Server error while pushing stock for {product.sku} to {listing.channel}: {e}")
                listing.needs_push = True
                listing.push_attempts += 1
                listing.last_push_error = str(e)

            if status_code == 400:
                logger.error(f"Bad request error while pushing stock for {product.sku} to {listing.channel}: {e}")
                listing.needs_push = True
                listing.push_attempts = 5
                listing.last_push_error = str(e)

            if status_code == 401:
                logger.warning(f"Unauthorized error while pushing stock for {product.sku} to {listing.channel}: {e}")
                listing.needs_push = True
                listing.push_attempts = 5
                listing.last_push_error = str(e)

            if status_code == 403:
                logger.warning(f"Forbidden error while pushing stock for {product.sku} to {listing.channel}: {e}")
                listing.needs_push = True
                listing.push_attempts = 5
                listing.last_push_error = str(e)

            if status_code == 404:
                logger.warning(f"Not found error while pushing stock for {product.sku} to {listing.channel}: {e}")
                listing.needs_push = True
                listing.push_attempts = 5
                listing.last_push_error = str(e)


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

"""Database setup: connection + table definitions for the hub."""
import os
from datetime import datetime

from dotenv import load_dotenv
from sqlalchemy import (Column, DateTime, ForeignKey, Integer, Numeric, String,
                        Text, UniqueConstraint, create_engine)
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()
engine = create_engine(os.environ["DATABASE_URL"], echo=False)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class Product(Base):
    """Master product record. `stock` here is the single source of truth."""
    __tablename__ = "products"
    id = Column(Integer, primary_key=True)
    sku = Column(String(32), unique=True, nullable=False)
    name = Column(String(200), nullable=False)
    category = Column(String(80))
    price = Column(Numeric(10, 2), nullable=False)
    stock = Column(Integer, nullable=False, default=0)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class ChannelListing(Base):
    """Where a product is published, and its ID on that channel."""
    __tablename__ = "channel_listings"
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    channel = Column(String(32), nullable=False)        # "woocommerce" | "marketplace"
    external_id = Column(String(64))                    # the channel's own product ID
    title = Column(String(200))
    last_synced_at = Column(DateTime)
    __table_args__ = (UniqueConstraint("product_id", "channel"),)


class Order(Base):
    """Orders pulled from every channel into one table."""
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True)
    channel = Column(String(32), nullable=False)
    external_id = Column(String(64), nullable=False)    # the channel's order ID
    sku = Column(String(32), nullable=False)
    qty = Column(Integer, nullable=False)
    total = Column(Numeric(10, 2))
    status = Column(String(32), default="pending")      # pending | shipped | delivered | rejected
    created_at = Column(DateTime, default=datetime.utcnow)
    # Same order pulled twice = same row, so a sale is never counted twice.
    __table_args__ = (UniqueConstraint("channel", "external_id"),)


class StockEvent(Base):
    """Audit log of every stock change. Feeds the dashboard and helps debugging."""
    __tablename__ = "stock_events"
    id = Column(Integer, primary_key=True)
    sku = Column(String(32), nullable=False)
    change = Column(Integer, nullable=False)            # -2 = sold two, +10 = restocked ten
    reason = Column(String(64))                         # "sale", "restock", "rejected_oversell"
    channel = Column(String(32))
    created_at = Column(DateTime, default=datetime.utcnow)


def init_db():
    Base.metadata.create_all(engine)

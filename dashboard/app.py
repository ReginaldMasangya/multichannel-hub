"""Streamlit frontend.  Run from the project folder:  streamlit run dashboard/app.py
Talks only to the hub API (never to the channels directly)."""
import os

import httpx
import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv

load_dotenv()
HUB = os.getenv("HUB_URL", "http://localhost:8000")

st.set_page_config(page_title="Multichannel Hub", layout="wide")
page = st.sidebar.radio("Page", ["Products", "Orders", "Dashboard"])


def get(path):
    return httpx.get(f"{HUB}{path}", timeout=30).json()


if page == "Products":
    st.title("Products")
    df = pd.DataFrame(get("/products"))
    st.dataframe(df, use_container_width=True, hide_index=True)
    sku = st.selectbox("Publish to all channels", df["sku"] if not df.empty else [])
    if st.button("Publish") and sku:
        st.write(httpx.post(f"{HUB}/products/{sku}/publish", timeout=60).json())
    # TODO (Wed): bulk CSV upload with st.file_uploader

elif page == "Orders":
    st.title("Orders (all channels)")
    if st.button("Sync orders now"):
        st.write(httpx.post(f"{HUB}/sync/orders", timeout=60).json())
    st.dataframe(pd.DataFrame(get("/orders")), use_container_width=True, hide_index=True)

else:
    st.title("Dashboard")
    orders = pd.DataFrame(get("/orders"))
    if orders.empty:
        st.info("No orders yet. Place a test order on a channel, then sync.")
    else:
        st.plotly_chart(px.bar(orders.groupby("channel", as_index=False)["total"].sum(),
                               x="channel", y="total", title="Sales by channel"),
                        use_container_width=True)
    # TODO (Thu): 3 shared filters (channel, date range, category) + 3 more charts
    st.link_button("Download orders (XLSX)", f"{HUB}/export?table=orders&format=xlsx")

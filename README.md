# Multichannel Hub

One hub that publishes products to two sales channels, pulls their orders, and keeps stock in sync so the last unit is never sold twice.

- **Channel A:** WooCommerce (brand webstore)
- **Channel B:** PrestaShop (standing in for the marketplace)
- **Hub:** FastAPI + PostgreSQL
- **AI:** Gemini adapts each listing to its channel
- **Frontend:** Streamlit (products, orders, dashboard, export)

All tools are free and open source. All data is synthetic.

## Setup (Windows, Command Prompt)

1. Install Docker Desktop and Git. Python 3.11+ is only needed to run code outside Docker.
2. Copy `.env.example` to `.env` and add your `GEMINI_API_KEY`.
3. Start everything. The first run downloads and installs for several minutes:
   ```
   docker compose up -d --build
   ```
4. Set up WooCommerce:
   - Open http://localhost:8080 and finish the WordPress install.
   - Plugins → Add New → install and activate **WooCommerce**.
   - Settings → Permalinks → choose **Post name** (needed for the REST API).
   - WooCommerce → Settings → Advanced → REST API → add a key with Read/Write.
   - Paste the key and secret into `.env`.
5. Set up PrestaShop:
   - Open http://localhost:8081/admin-hub and log in with `admin@example.com` / `HubDemo2026!`.
   - Advanced Parameters → Webservice → set **Enable PrestaShop's webservice** to Yes and save.
   - Click **Add new webservice key**, then **Generate**.
   - Give it these permissions:
     - View, Add, Modify: `products`, `stock_availables`
     - View: `orders`
     - Add: `order_histories`
   - Save, then paste the key into `PRESTASHOP_API_KEY` in `.env`.
   - Shipping → Carriers → edit **Click and collect** → **Shipping locations and costs** → tick the **Asia** zone and finish. Without this, checkout has no delivery option for the Philippines.
   - When placing test orders, use a Philippine address. Bank wire is only offered there.
6. Restart the apps so they read the new keys:
   ```
   docker compose up -d --force-recreate hub dashboard
   ```
7. Load the demo data, in this order:
   ```
   docker compose exec hub python -m hub.seed --channels
   ```
   Then click **Import from channels** on the Products page (http://localhost:8501), and run:
   ```
   docker compose exec hub python -m hub.seed --history
   ```
   Run `--channels` only once. Running it again creates duplicate products.

After changing code, rebuild with `docker compose up -d --build`.

### Running the apps outside Docker (optional)

```
docker compose stop hub dashboard
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn hub.main:app --reload        (terminal 1)
streamlit run dashboard/app.py       (terminal 2)
```

## Ports

| Service | URL |
|---|---|
| Hub API (docs at `/docs`) | http://localhost:8000 |
| Frontend | http://localhost:8501 |
| WooCommerce | http://localhost:8080 |
| PrestaShop shop | http://localhost:8081 |
| PrestaShop admin | http://localhost:8081/admin-hub |
| Hub Postgres | localhost:5433 (user/pass/db: hub) |

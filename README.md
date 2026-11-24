# Multichannel Hub

One hub that publishes products to two sales channels, pulls their orders, and keeps stock in sync so the last unit is never sold twice.

- **Channel A:** WooCommerce (brand webstore)
- **Channel B:** Mock marketplace (JSON Server)
- **Hub:** FastAPI + PostgreSQL
- **AI:** Gemini adapts each listing to its channel
- **Frontend:** Streamlit (products, orders, dashboard, export)

All tools are free and open source. All data is synthetic.

## Setup (Windows, Command Prompt)

1. Install Docker Desktop, Python 3.11+, Node.js and Git.
2. In the project folder, create and activate the virtual environment:
   ```
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and add your `GEMINI_API_KEY`.
4. Start the databases, WooCommerce and the mock marketplace:
   ```
   docker compose up -d
   ```
5. Set up WooCommerce:
   - Open http://localhost:8080 and finish the WordPress install.
   - Plugins → Add New → install and activate **WooCommerce**.
   - Settings → Permalinks → choose **Post name** (needed for the REST API).
   - WooCommerce → Settings → Advanced → REST API → add a key with Read/Write.
   - Paste the key and secret into `.env`.
6. Load the demo products:
   ```
   python -m hub.seed
   ```
7. Run the hub (terminal 1) and the frontend (terminal 2):
   ```
   uvicorn hub.main:app --reload
   streamlit run dashboard/app.py
   ```
   Hub API docs: http://localhost:8000/docs · Frontend: http://localhost:8501

## Ports

| Service | URL |
|---|---|
| Hub API | http://localhost:8000 |
| Frontend | http://localhost:8501 |
| WooCommerce | http://localhost:8080 |
| Mock marketplace | http://localhost:3001 |
| Hub Postgres | localhost:5433 (user/pass/db: hub) |

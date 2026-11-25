# Multichannel E-Commerce Build Plan

Nov 23, 2026 · @Reginald

> Local copy of the plan doc: https://claude.ai/artifact/ARgoLvxQxQJYHZVVebo5rr
> The doc is the source of truth; this file was exported from it on 25 Nov 2026.

## Summary

Build a small FastAPI **hub** that owns the master product list and stock. Connect it to two real stores: a **WooCommerce** webstore and a **PrestaShop** store standing in for the marketplace. A **cron worker** in Docker keeps listings and stock in sync. Put a **Streamlit** dashboard on top.

This covers every mandatory item on slide 22 (Solution 13, Stretch level). It fits in three build days and reuses tools already known: FastAPI and Postgres.

**Demo:** Friday 27 November 2026, about 10 minutes. **Submit:** repo link plus a one-page setup note.

## Architecture

- **Hub (FastAPI + Postgres):** the single source of truth for products, stock and orders.
- **Channel A, brand webstore:** WooCommerce in Docker. A real shop with a REST API (a way for programs to read and change its data) and webhooks (automatic messages the shop sends when an order happens).
- **Channel B, marketplace:** PrestaShop in Docker (with its own MySQL database), standing in for Shopee/Lazada. A real, free shop with a webservice API (PrestaShop's built-in API for reading and changing products, stock and orders). It has no built-in webhooks, so it is polled.
- **Sync worker (cron in Docker):** a small `worker` container runs the sync job on a cron schedule (a timetable that says when to run a command). Cron starts the job once a minute, the smallest step it allows. Each run then does three sync passes, 20 seconds apart: poll both channels for new orders, retry failed pushes, wait. After the third pass it exits. Woo webhooks still bring orders in instantly. A 20-second delay counts as near real-time.
- **LLM (Gemini free tier or Groq):** rewrites one master listing into each channel's style.
- **Streamlit app (two pages):** a **Products** page to create, publish, edit, bulk upload and import listings, which only calls the hub API; and a **Dashboard** page with charts, filters and export, which only reads the database. Both work on a phone for the web and mobile requirement.

**Why PrestaShop instead of JSON Server or Medusa?** JSON Server only fakes an API. PrestaShop is a real, free, open-source shop with an official Docker image, so both channels are genuine stores. Medusa needs Postgres, Redis and more setup than the schedule can spare.

**Rule:** always push the *absolute* stock number to channels ("set to 7"), never a change ("minus 1"). If a push is lost or repeated, the next sync still corrects it.

**Cron rule:** wrap the job in `flock` (a lock file), so a slow run never overlaps the next one. If a run is still busy when the next minute starts, the new run sees the lock and skips. Two runs at once could apply the same order twice or push stale stock.

## Components and responsibilities

| Component | Job | Does not |
| --- | --- | --- |
| Hub (FastAPI) | The brain: owns products and stock, publishes, edits, imports, applies orders, pushes stock and order status | Take customer purchases |
| Database (Postgres) | The hub's memory: products, listings, orders, stock history, sync cursors | Run any logic |
| Cron worker | The heartbeat: a cron job in its own container starts once a minute and syncs every 20 s, polls channels, retries failed pushes | Make decisions; it calls the hub's functions |
| Channel adapters | Translators: same methods for every channel (import, create, update, set stock, fetch orders, update status) | Store data or decide anything |
| WooCommerce | Real webstore: sells, sends webhooks, accepts hub updates | Decide stock; its number is a copy |
| PrestaShop | Second real store, standing in for Shopee/Lazada; demo orders are placed on its storefront | Send webhooks (none built in); it is polled |
| LLM (Gemini) | Copywriter: rewrites a listing per channel | Decide price or stock |
| Products page | Remote control: sends requests to the hub API | Write to the database directly |
| Dashboard page | Window: charts, filters, export | Change any data |

## Data direction

| Data | Direction | Source of truth |
| --- | --- | --- |
| Products, prices, listing text | Hub → channels | Hub |
| Stock numbers | Hub → channels | Hub |
| Orders | Channels → hub | Channel where the sale happened |
| Delivery status | Channels → hub | Channel |
| Order status changes (e.g. shipped) | Hub → the order's channel only | Hub |
| Existing listings | Channels → hub, once (import) | Hub after import |

**Import rule:** match products by SKU. New SKU → create the product and its listing. Known SKU → only add the new channel's listing. If channels disagree on stock, take the lower number, then push it to all channels.

**Order flow:** order arrives (Woo: webhook + polling; PrestaShop: polling) → skip if already saved → lock the product row, subtract stock, log a stock movement → push the full stock number to every listing of that SKU → dashboard shows it within 10 seconds (auto-refresh).

## Retry policy

A failed stock push sets `needs_push = TRUE` and saves the error in `last_push_error`. The cron job retries on every sync pass (every 20 seconds), always sending the hub's current stock number, so one successful retry fixes every missed update.

1. **Sort errors by type.** Temporary errors (timeouts, connection errors, HTTP 5xx, 429) add 1 to `push_attempts`. Permanent errors (HTTP 400, 401, 403, 404) set `push_attempts` to the cap right away.
2. **Cap attempts at 5.** The cron job only retries listings where `needs_push AND push_attempts < 5`.
3. **Park and show.** Listings at the cap appear in a "Failed pushes" section on the Products page with their error and a Retry button. Retry calls `POST /listings/{channel}/{external_id}/retry`, which resets `push_attempts` to 0 and pushes again.
4. **On success:** reset `needs_push`, `push_attempts` and `last_push_error`.

Failed publishes (`status='failed'`) also get a Retry button on the Products page.

**Optional demo moment:** `docker compose stop prestashop`, make a Woo sale, start PrestaShop again; its stock corrects on the next sync pass, within 20 seconds.

## Synthetic data and seeding

The channels must hold data for import and order fetching to return anything, so seeding happens in two places.

| What | Where it goes | Why |
| --- | --- | --- |
| ~25 products on Woo, ~25 in PrestaShop, ~10 overlapping SKUs with different stock | The channels (Woo REST API, PrestaShop webservice) | The hub starts empty and runs Import, proving SKU matching and the lower-stock rule |
| ~50 past orders over 30 days, plus stock movements | The hub database directly | Gives the dashboard history to show |
| New orders | Placed live on both storefronts: Cash on delivery on Woo, Bank wire on PrestaShop | Proves sync end to end |

After `--history`, set each channel's `sync_state.last_synced_at` to now, so the worker treats past orders as already handled.

**What fetching returns:** `import_listings()` returns the seeded channel products. `fetch_orders()` returns nothing on its first run after seeding, then only the orders placed live during the demo.

**Simulate marketplace sale:** creating a PrestaShop order through the webservice needs a customer, an address and a cart first. Simpler: place demo orders on the PrestaShop storefront. Add a button only if time allows.

**Trade-off:** past orders exist only in the hub, not on the channels. Say so in the demo: "History is pre-loaded for the dashboard; everything from now on is live." Creating back-dated orders on Woo is untested, so it's out of scope.

## Data model

| Table | Columns |
| --- | --- |
| products | sku, title, description, price, category, stock |
| channel_listings | sku, channel, external_id, channel_title, channel_description, channel_price, status, needs_push, push_attempts, last_push_error |
| orders | channel, external_id, sku, qty, status, delivery_status, created_at |
| stock_movements | sku, delta, reason, channel, timestamp |
| sync_state | channel, last_synced_at |

`stock_movements` is a ledger: every stock change is a new row, not an overwrite. Example: "−2, sale, marketplace, 10:42". It proves sync history in the demo and feeds the dashboard.

Extra rules in the schema: `orders` has a unique constraint on `(channel, external_id)`, so an order delivered twice (webhook + poll) is saved once. `channel_listings` tracks failed stock pushes with `needs_push`, `push_attempts` and `last_push_error` (see Retry policy). `channel_description` stores the LLM's rewritten description for each channel.

## Tasks

Every task needed before the demo on Friday 27 November, in rough build order. Tick each one off as it lands.

- [ ] Create the repo with one `docker-compose.yml`: Postgres, WordPress + WooCommerce, PrestaShop + MySQL, hub, cron `worker`, Streamlit.
- [x] Turn on the Woo REST API and generate test API keys.
- [ ] Turn on the PrestaShop webservice and create an API key.
- [ ] Write `seed.py` with Faker, in two modes (see Synthetic data and seeding): `--channels` puts products on Woo and PrestaShop; `--history` puts about 50 past orders into the hub.
- [x] Hub endpoints: `GET/POST /products`, `GET /orders`.
- [x] Add `sync_state`, the unique constraint on orders and the `needs_push` flag.
- [ ] **PrestaShop adapter:** rewrite `hub/channels/marketplace.py` against the PrestaShop webservice.
- [ ] **Cron worker:** a `worker` service runs `hub/sync.py` every minute with cron, does three passes 20 seconds apart, and is wrapped in `flock`.
- [ ] **Publish:** `POST /products/{sku}/publish` creates the listing on both channels and stores the external IDs. If one channel fails, keep going: save the successes, mark the failure `status='failed'` for retry, and return both lists.
- [ ] **Edit:** changing price or title in the hub pushes to both channels.
- [ ] **Bulk upload:** a CSV upload creates many products, then publishes them.
- [x] **Import:** `import_listings()` on each adapter reads existing products from Woo and PrestaShop, matches them by SKU, and sets one stock number (the lower one).
- [ ] **Products page:** Streamlit page with a product table, add form with "publish now", edit form, publish buttons, CSV upload and an import button. It calls the hub API only.
- [ ] **Retry handling:** error sorting in `push_stock()` (written by Reginald), the 5-attempt cap in the cron job, the retry endpoint, and a "Failed pushes" section with Retry buttons on the Products page.
- [ ] **Fetch:** the cron job pulls new orders and delivery status from both channels.
- [x] **Inventory sync:** an order on one channel lowers hub stock, then pushes the new quantity to the other.
- [ ] **Push back:** a status change in the hub (e.g. shipped) updates the channel order.
- [ ] **LLM adapter:** one call per channel. Marketplace: keyword-heavy title, 120 characters max. Webstore: brand-voice copy.
- [ ] **Dashboard charts:** 4+ charts: sales by channel over time, orders by channel, top SKUs, stock levels with a low-stock line.
- [ ] **Dashboard filters:** channel, date range and category on every chart.
- [ ] **Dashboard auto-refresh:** wrap the charts in `@st.fragment(run_every="10s")` so they rerun every 10 seconds without a page reload. Needs Streamlit 1.37 or newer.
- [ ] **"Last synced" label:** show "Last synced 12 s ago" on the Dashboard, read from `sync_state.last_synced_at`.
- [x] **Export:** CSV and XLSX with pandas.
- [ ] Tick every slide-22 item against the checklist below. Fix gaps.
- [ ] Write the one-page setup note: `docker compose up` → Woo and PrestaShop setup steps (API keys) → `python seed.py --channels` → click Import on the Products page → `python seed.py --history`. Rerun it from a clean clone.
- [ ] Cache the LLM output for the demo product.
- [ ] Rehearse the demo twice with a timer.

## Demo script (Fri 27 Nov, ~10 min)

1. One-minute story: an SME sells on Shopee and its own site, oversells, and re-types listings by hand.
2. On the Products page, show the imported listings, then add one product with "publish now" ticked. It appears on both channels with AI-adapted copy.
3. Buy it on the Woo store. Stock drops on PrestaShop within 20 seconds (the next sync pass).
4. Open the dashboard on a phone. Watch the new sale appear by itself within about 10 seconds. Filter by channel. Export to XLSX.
5. Stretch, only if time allows: a picking-list PDF from today's orders.

## Requirement checklist (slide 22)

- [ ] At least 2 channels (marketplace + brand webstore) in one dashboard
- [ ] Real-time or near real-time view of sales, orders and inventory
- [ ] Create and edit listings across channels, with bulk upload
- [ ] Fetch listings, orders and delivery status from channels and push data back
- [ ] Inventory syncs as sales happen across channels
- [ ] Dashboard of sales and orders across channels
- [ ] Repeat requirement: 4+ charts and 3 filters on every chart
- [ ] Repeat requirement: works on web and mobile
- [ ] Repeat requirement: export to CSV and XLSX
- [ ] 30–50 synthetic records seeded; no real data
- [ ] Free tools only
- [ ] Repo link and one-page setup note submitted

## Scorecard, risks and open questions

| Criterion | Weight | How this plan scores |
| --- | --- | --- |
| Requirement coverage | 40% | The task list maps 1:1 to slide 22 |
| Working live flow | 30% | Runs locally in Docker; LLM output cached, so venue Wi-Fi can't break it |
| Free tools, repeatable setup | 15% | All open-source or free tier; setup note rerun from a clean clone |
| Business story | 15% | Hook: "no more overselling" |

### Risks

- **Overselling race:** both channels sell the last unit before sync runs. The hub's `apply_order()` must decide: cancel the later order, or allow negative stock and flag it. Good talking point for judges.
- **WooCommerce setup time:** if Docker setup drags past Tuesday noon, swap Woo for a second mock channel and keep moving.
- **LLM rate limits:** free tiers can throttle. Cache results and fall back to the original listing text.
- **Woo webhooks to a local address:** WordPress may block webhook delivery to internal Docker hostnames. If so, skip webhooks; 20-second polling still meets near real-time.
- **PrestaShop API quirks:** the webservice answers in XML unless you add `output_format=JSON`. Stock lives in the `stock_availables` resource, not on the product. Budget time to learn these.
- **Slow sync passes:** the three passes must fit inside one minute. If a pass runs long (for example, a channel times out), the run overlaps the next minute, and `flock` makes that next run skip. Keep request timeouts short, around 5 seconds, so one slow channel can't stall a whole run.

### Open questions

- Confirm with Gareth or Aaron that PrestaShop can stand in for the marketplace channel.

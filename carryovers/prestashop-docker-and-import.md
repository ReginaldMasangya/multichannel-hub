# Carryover — branch `prestashop-docker-and-import` (not yet merged into `main`)

Session date: Wed 25 Nov 2026. Demo: Fri 27 Nov.

## What this branch delivered

- `d70a019`: `POST /products/import`, `import_listings()` on both adapters, Import button, `apply_sale()` oversell policy, plan and notes.
- `4c8a68f`:
  - PrestaShop replaces the JSON Server mock; `hub/channels/marketplace.py` rewritten.
  - Hub and dashboard run in Docker (`Dockerfile`, `.dockerignore`).
  - Import pushes merged stock back to the stores and reports `push_failed`.
  - Both adapters skip dead orders (`is_sale()`).
  - `--history` no longer changes current stock, sets `sync_state`, only uses channels that list the product, and won't run twice.
  - README setup steps and `.env.example` updated.

## What was tested

| What | How |
| --- | --- |
| PrestaShop import, create, set stock, fetch order, cancel order | Real store |
| Import stock push to both stores | Real stores, 46 listings matched |
| `--channels` and `--history` | Real data, read back |
| Woo dead-order filter | Fake server only |
| Failed-push reporting in Import | Fake clients only |

The fake-server test scripts were temporary and are not in the repo.

## Current data

- Hub: 36 products, 46 listings, 50 made-up past orders (`SEED-`) with matching stock events. The first 50 were replaced because 20 used a channel that didn't list the product.
- WooCommerce: 25 products, no orders at the last check (before seeding).
- PrestaShop: 21 seeded products plus its `demo_` samples (the adapter skips them). One cancelled test order. `TEST-001` was deleted.
- Don't run `--channels` again: it creates duplicates.

## Local setup notes

- Start with `docker compose up -d --build`. Rebuild after code changes.
- PrestaShop checkout needs the Asia zone on the "Click and collect" carrier and a Philippine buyer address (Bank wire is limited to the Philippines). The carrier step is in the README.
- Inside Docker the adapter sends `PRESTASHOP_HOST`, or PrestaShop redirects the request.
- `.env`: `PRESTASHOP_URL` must not end in `/api` (it did during this session; only matters outside Docker). The old `MARKETPLACE_URL` is unused.
- The admin and database passwords in `docker-compose.yml` and the README are local demo values only.

## Not finished — carry over

Known bugs and gaps:

1. An order cancelled **after** the hub counted it doesn't get its stock restored (both channels). The next push could then set the store's stock too low.
2. `pull_orders()` doesn't use `sync_state` (neither reads nor updates it); it only skips orders already saved. It reads only the newest 50 orders per store.
3. `push_stock_everywhere()` records only timeouts, connection errors, and HTTP 400/401/403/404/429/5xx. Other HTTP errors are silently ignored.
4. Nothing enforces the 5-attempt retry cap.
5. Publish: if the second channel fails, the first listing is created in the store but not saved in the hub, so a retry would duplicate it.
6. `woocommerce.update_order_status()` sends the status unchanged, but `shipped` and `rejected` are not built-in WooCommerce statuses. Needs a mapping for Push back. PrestaShop's version is only tested for cancelling.
7. Import doesn't save categories (all 36 are empty), which blocks the dashboard category filter.
8. Imported Woo descriptions contain HTML tags (25 products).

Not built: cron `worker` container, delivery status, Edit, Bulk upload, Products page forms, retry endpoint and "Failed pushes" section, dashboard work (see `progress.md`).

Before the demo:

- Set both stores' currency to PHP (last seen: Woo USD, PrestaShop EUR; prices aren't converted).
- Confirm PrestaShop as the marketplace with Gareth/Aaron.
- Decide the marketplace title limit (60 vs 120).

Cleanup (optional): the stopped `multichannel-hub-marketplace-1` container and the `mock-marketplace/` folder are no longer used.

## Next session should start with

1. **Fetch + cron worker.** Place a real order on WooCommerce and one on PrestaShop, then check that the other store's stock updates. This also tests the Woo filter. Handle bugs 1 and 2 here.
2. **Publish** (bug 5), then the **Products page**.

# Build progress

Last updated: Wed 25 Nov 2026, end of the `prestashop-docker-and-import` session.

Channel B changed from the JSON Server mock to PrestaShop (see `PLAN.md`).

## Tuesday 24 Nov — done (5/5)

- [x] docker-compose.yml: Postgres, WooCommerce, mock marketplace, hub, Streamlit
- [x] WooCommerce REST API turned on, test keys in `.env`
- [x] `hub/seed.py` — two modes (`--channels`, `--history`)
- [x] Hub endpoints — `GET/POST /products`, `GET /orders`
- [x] Schema — `sync_state` table, `needs_push`/`push_attempts`/`last_push_error` columns, unique constraint on orders (applied to the live `hub-db`)

Correction: the compose file did not actually include the hub or Streamlit on Tuesday. Both were added Wednesday.

## Foundations for PrestaShop — done 25 Nov

- [x] `docker-compose.yml`: PrestaShop + MySQL, hub and dashboard containers (new `Dockerfile`). The `worker` container is still to do, with the cron task.
- [x] PrestaShop webservice turned on, key in `.env`
- [x] PrestaShop adapter (`hub/channels/marketplace.py`). Tested on the real store: import, create product, set stock, fetch order, cancel order.
- [x] Demo data loaded: 36 products, 46 listings (25 Woo, 21 PrestaShop), 50 past orders. All 46 listing stocks matched the hub at the last check.

## Wednesday 25 Nov — 3 done, 4 partial, 3 not started

- [x] Import — merges by SKU, lower stock wins, and pushes that number back to the channels. Verified on both real stores.
- [x] `apply_sale()` (`hub/sync.py`) — rejects oversells. Not yet run against a real order.
- [~] Publish — endpoint exists, but doesn't keep going if one channel fails, and there's no `status` column (plan calls for `status='failed'`)
- [ ] Edit — push price/title changes to both channels
- [ ] Bulk upload — CSV → create many products → publish
- [~] Products page — table, publish button and import button exist; no add form, edit form or CSV upload
- [~] Retry handling — error sorting written; no 5-attempt cap, no retry endpoint, no "Failed pushes" section
- [~] Fetch — manual trigger only; no ~20s cron worker; no delivery status. Both adapters now skip dead orders.
- [ ] Push back — hub order-status change updating the channel
- [x] LLM adapter — done; marketplace title cap is 60 characters in `hub/llm.py`, plan says 120 (unsettled)

Inventory sync is ticked in `PLAN.md`: the code exists, but a real sale has not yet gone through the hub to the other store.

## Thursday 26 Nov

- [x] CSV/XLSX export — done early (built Tuesday)
- [ ] Dashboard: 4+ charts (sales by channel over time, orders by channel, top SKUs, stock levels with low-stock line) — only 1 chart exists
- [ ] 3 filters on every chart (channel, date range, category)
- [ ] Dashboard auto-refresh every 10 s, and "Last synced" label
- [ ] QA pass: tick every slide-22 item, fix gaps
- [ ] One-page setup note, rerun from a clean clone (README updated 25 Nov, not yet rerun from a clean clone)
- [ ] Cache LLM output for the demo product
- [ ] Rehearse demo twice with a timer

## Overall

Foundations and demo data are in place. Next most important: the live flow (Fetch + cron worker, then Publish and the Products page), which the Friday demo depends on.

## Open / unsettled

- Marketplace LLM title character limit: code (60) vs plan (120) — needs a decision.
- PrestaShop standing in for the marketplace — confirm with Gareth/Aaron (open in the plan doc).
- `PLAN.md` task ticks were not updated this session. The online plan doc is the source of truth.

Details and known bugs: `carryovers/prestashop-docker-and-import.md`.

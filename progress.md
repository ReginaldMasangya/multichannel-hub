# Build progress

Last updated: Tue 24 Nov 2026, end of day.

## Tuesday 24 Nov — done (5/5)

- [x] docker-compose.yml: Postgres, WooCommerce, mock marketplace, hub, Streamlit
- [x] WooCommerce REST API turned on, test keys in `.env`
- [x] `hub/seed.py` — two modes (`--channels`, `--history`)
- [x] Hub endpoints — `GET/POST /products`, `GET /orders`
- [x] Schema — `sync_state` table, `needs_push`/`push_attempts`/`last_push_error` columns, unique constraint on orders (applied to the live `hub-db`)

## Wednesday 25 Nov — ~30%, not yet started as of this writing

- [ ] **Import** — `import_listings()` on each channel adapter, matched by SKU, lower stock wins. **Blocking: nothing new enters the hub without this.**
- [ ] **apply_sale()** (`hub/sync.py`) — oversell policy. **Blocking: still `raise NotImplementedError`; crashes order sync on any real order.**
- [~] Publish — endpoint exists, but doesn't keep going if one channel's push fails, and there's no `status` column (plan calls for `status='failed'`)
- [ ] Edit — push price/title changes to both channels
- [ ] Bulk upload — CSV → create many products → publish
- [~] Products page — table + single-SKU publish button exist; no add form, edit form, CSV upload, or import button
- [~] Retry handling — error classification written; no 5-attempt cap enforcement, no retry endpoint, no "Failed pushes" UI section
- [~] Fetch — works, but only on manual trigger; no automatic ~20s polling worker
- [ ] Push back — hub order-status change updating the channel
- [x] LLM adapter — done; one open mismatch: marketplace title cap is 60 chars in `hub/llm.py`, plan says 120 (unsettled)

## Thursday 26 Nov — ~20%

- [x] CSV/XLSX export — done early (built Tuesday)
- [ ] Dashboard: 4+ charts (sales by channel over time, orders by channel, top SKUs, stock levels with low-stock line) — only 1 chart exists
- [ ] 3 filters on every chart (channel, date range, category)
- [ ] QA pass: tick every slide-22 item, fix gaps
- [ ] One-page setup note, rerun from a clean clone
- [ ] Cache LLM output for the demo product
- [ ] Rehearse demo twice with a timer

## Overall

Roughly 40-45% of the full build, by item count. Import and `apply_sale()` are the two items most worth prioritizing — nearly everything else on Wednesday and Thursday assumes they're done first.

## Open / unsettled

- Marketplace LLM title character limit: code (60) vs plan (120) — needs a decision.
- Mock marketplace counting as a "real channel" for GECO — still open with Gareth/Aaron per the plan doc.

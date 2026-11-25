# Carryover — branch `tuesday-tasks` (merged into `main` @ ac53873)

## What this branch delivered

- `hub/seed.py` rewrite: two modes (`--channels`, `--history`), replacing the old CSV-straight-to-hub loader. `_overlap_stock()` written by Reginald.
- `hub/db.py`: added `SyncState` table and `needs_push`/`push_attempts`/`last_push_error` columns on `ChannelListing`.
- `hub/sync.py`: `push_stock_everywhere()` now catches per-channel push failures and classifies temporary vs permanent errors (error-sorting logic written by Reginald).
- `hub/main.py`: added `POST /products` to create a new product directly in the hub (separate from the existing publish endpoint).
- `hub-db` was recreated (volume wiped, old schema gone) and the new schema applied by starting `uvicorn hub.main:app --reload`. The database is currently empty — no seed data loaded yet.

## Not finished on this branch — carry over

- `apply_sale()` in `hub/sync.py` still raises `NotImplementedError` (pre-existing TODO, untouched here). Blocks inventory sync; crashes `pull_orders()` on any real order.
- Retry logic records `push_attempts` but nothing enforces the 5-attempt cap — it climbs indefinitely with no stopping behavior.
- No `status` column on `ChannelListing`. The plan's Wednesday item #1 calls for `status='failed'`; schema only has `needs_push` instead.
- Marketplace LLM title cap mismatch: `hub/llm.py`'s `CHANNEL_STYLE` says 60 characters; the plan says 120. Unresolved — pick one.
- No automatic polling worker — order sync only runs on manual trigger (`POST /sync/orders` or the dashboard button).

## Next branch should start with

1. **Import** (`import_listings()` on both channel adapters + a merge endpoint + a Products page button) — highest priority, almost everything else on Wednesday assumes products are already in the hub.
2. **`apply_sale()`** — second priority, blocks inventory sync and crashes order sync today.

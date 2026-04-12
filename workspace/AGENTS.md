# CaptureIQ Agent Operating Instructions

## Database Schema (condensed — canonical against `app/src/db/migrations/2026-04-06-phase-1-schema.sql`)

All primary keys are `UUID` (via `uuid_generate_v4()`), not serial. The ONLY
exception is `users.id`, which is `TEXT` because it stores the Clerk user id
(e.g. `user_abc123`).

### opportunities (core table — 40+ columns)

Identity + source
- `id UUID PK`
- `source TEXT NOT NULL` — BidBuy, HigherEd, Gateway
- `source_id TEXT NOT NULL`
- **UNIQUE (source, source_id)** — idempotent upsert key for ALL ingestion writes

Core fields
- `title TEXT NOT NULL`
- `description TEXT`
- `solicitation_type TEXT` — RFP, RFQ, IFB, RFI
- `contract_type TEXT`

Buyer
- `buying_organization TEXT` — free-text agency name (NOT called `agency`)
- `buyer_id UUID REFERENCES buyers(id)`
- `org_type TEXT`
- `location TEXT`

Financials (NOT `value_min`/`value_max`)
- `estimated_value NUMERIC(18,2)`
- `currency TEXT NOT NULL DEFAULT 'USD'`
- `award_amount NUMERIC(18,2)`
- `awarded_to TEXT`

Dates — all `TIMESTAMPTZ`
- `post_date`, `due_date`, `close_date`, `award_date`

Status + amendments
- `status TEXT NOT NULL DEFAULT 'active'` — active, closed, awarded, cancelled
- `amendment_count INTEGER NOT NULL DEFAULT 0`
- `last_amended_at TIMESTAMPTZ`

Scoring (populated by Epic 3)
- `fit_score INTEGER` — 0–100
- `fit_classification TEXT` — HOT, HIGH, MEDIUM, LOW, NO_FIT  ← this is the "tier", not a `tier` column
- `confidence_score NUMERIC(4,3)`
- `scored_at TIMESTAMPTZ`
- `scoring_version TEXT`

Classification
- `service_lines TEXT[] NOT NULL DEFAULT '{}'`
- `keyword_matches JSONB`
- `nigp_codes TEXT[] NOT NULL DEFAULT '{}'`
- `naics_codes TEXT[] NOT NULL DEFAULT '{}'`
- `set_aside_flags TEXT[] NOT NULL DEFAULT '{}'`
- `risk_flags JSONB`

Flags
- `is_excluded BOOLEAN NOT NULL DEFAULT FALSE`
- `exclusion_reason TEXT`
- `is_duplicate BOOLEAN NOT NULL DEFAULT FALSE`

Contact + links
- `contact_name`, `contact_email`, `contact_phone TEXT`
- `source_url`, `documents_url TEXT`

Data lineage
- `raw_payload JSONB` — preserve as-ingested payload
- `normalized_at TIMESTAMPTZ`
- `search_vector TSVECTOR` — auto-maintained by trigger (DO NOT write directly)

Timestamps
- `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`

**NOT present in Phase 1:** `agency`, `tier`, `value_min`, `value_max`,
`ai_summary`, `requirements_extracted`. Do not write to these — they will fail.

### ingestion_logs (one row per connector run)

- `id UUID PK`
- `source TEXT NOT NULL`
- `run_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
- `status TEXT NOT NULL` — success, error, partial
- `records_found INTEGER NOT NULL DEFAULT 0`
- `records_inserted INTEGER NOT NULL DEFAULT 0`
- `records_updated INTEGER NOT NULL DEFAULT 0`
- `error_message TEXT` — NOT `error`
- `raw_payload JSONB` — full raw scraped response
- `duration_ms INTEGER`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`

**NOT present:** `records_scraped`, `records_new`, `records_duplicate`, `hot_alerts_sent`.
Use `records_found` for the scraped total and `records_inserted` for new rows.

### tasks (async queue — Next.js writes, agents poll)

- `id UUID PK`
- `task_type TEXT NOT NULL` — NOT `type`
- `payload JSONB NOT NULL DEFAULT '{}'`
- `status TEXT NOT NULL DEFAULT 'pending'` — pending, in_progress, done, failed
- `error_message TEXT` — NOT `error`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
- `picked_up_at TIMESTAMPTZ`
- `completed_at TIMESTAMPTZ`

### service_lines (seeded by Story 1.6)

- `id UUID PK`
- `name TEXT NOT NULL UNIQUE`
- `keywords TEXT[] NOT NULL DEFAULT '{}'`
- `nigp_patterns TEXT[] NOT NULL DEFAULT '{}'`
- `naics_codes TEXT[] NOT NULL DEFAULT '{}'`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`

### users (synced from Clerk by webhook)

- `id TEXT PK` — Clerk user_id (e.g. `user_abc123`)
- `email TEXT NOT NULL`
- `name TEXT`
- `role TEXT NOT NULL DEFAULT 'bd_analyst'`
- `created_at`, `updated_at TIMESTAMPTZ`

### buyers

- `id UUID PK`
- `name TEXT NOT NULL` — NOT unique (same agency name can span jurisdictions)
- `org_type`, `location`, `website TEXT`
- `contract_count INTEGER NOT NULL DEFAULT 0`
- `total_spend NUMERIC(18,2)`
- `relationship_owner TEXT` — Epic 9
- `notes TEXT`
- `created_at`, `updated_at TIMESTAMPTZ`

## Scoring Model (weighted keyword, MVP)

Tier thresholds map directly to `fit_classification`:
- `HOT` ≥ 85
- `HIGH` 65–84
- `MEDIUM` 40–64
- `LOW` < 40
- `NO_FIT` — excluded by filters before scoring

Scoring factors:
- Service line keyword match vs `service_lines.keywords`
- NIGP code match vs `service_lines.nigp_patterns`
- Dollar value (`estimated_value > 500000` = +10, `> 1000000` = +20)
- Due date runway (`due_date - NOW() < 14 days` = penalty −15)
- Agency relationship history (bonus if `buying_organization` matches a known `buyers.name`)

## Pipeline Instructions

### Ingest pipeline (per source)

1. Scrape source URL via Firecrawl MCP → markdown
2. Parse procurement records from markdown
3. Normalize each record to the `opportunities` schema above (use the CANONICAL column names — `buying_organization` not `agency`, `estimated_value` not `value_min`, `fit_classification` not `tier`)
4. Score using the weighted keyword model
5. `INSERT INTO opportunities ... ON CONFLICT (source, source_id) DO UPDATE SET <all mutable fields>, updated_at = NOW()`
6. If `fit_score >= 85` → send HOT alert via `agent-send` to Theo
7. Log the run into `ingestion_logs` with `status`, `records_found`, `records_inserted`, `records_updated`, `duration_ms`

### Task worker

1. `SELECT * FROM tasks WHERE status = 'pending' ORDER BY created_at LIMIT 5`
2. Execute based on `task_type`:
   - `refresh_source` → trigger Firecrawl scrape for that source
   - `score_opportunity` → re-score a specific opportunity by id
   - `pursue` → move to pursuit pipeline (Epic 7)
3. On success: `UPDATE tasks SET status='done', completed_at=NOW() WHERE id=$1`
4. On failure: `UPDATE tasks SET status='failed', error_message=$2, completed_at=NOW() WHERE id=$1`

### Daily digest (haiku)

1. `SELECT ... FROM opportunities WHERE created_at > NOW() - INTERVAL '24 hours' ORDER BY fit_score DESC LIMIT 20`
2. Format as short WhatsApp message
3. Send via `agent-send` to Theo

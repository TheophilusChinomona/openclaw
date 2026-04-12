# Tool Usage Conventions — CaptureIQ

## psql — Database Writes (ALL writes use this)

The Postgres MCP server is **read-only**. All INSERT/UPDATE/DELETE MUST use the
exec tool with `psql "$DATABASE_URL"`.

### Canonical idempotent upsert into opportunities

Column names must match `AGENTS.md` exactly — there is no `agency`, no `tier`,
no `value_min`, no `ai_summary` in Phase 1.

```bash
psql "$DATABASE_URL" <<'SQL'
INSERT INTO opportunities (
  source, source_id,
  title, description,
  buying_organization, org_type, location,
  estimated_value, currency,
  post_date, due_date,
  status,
  service_lines, nigp_codes, naics_codes,
  source_url, documents_url,
  raw_payload, normalized_at
) VALUES (
  'bidbuy', '12345',
  'IT Modernization Services', 'Scope of work...',
  'Illinois Department of Transportation', 'State', 'IL',
  2100000.00, 'USD',
  '2026-04-05T00:00:00Z', '2026-04-20T17:00:00Z',
  'active',
  ARRAY['it-consulting']::text[], ARRAY['920-18']::text[], ARRAY['541512']::text[],
  'https://bidbuy.illinois.gov/...', 'https://bidbuy.illinois.gov/docs/...',
  '{"raw":"..."}'::jsonb, NOW()
)
ON CONFLICT (source, source_id) DO UPDATE SET
  title               = EXCLUDED.title,
  description         = EXCLUDED.description,
  buying_organization = EXCLUDED.buying_organization,
  org_type            = EXCLUDED.org_type,
  location            = EXCLUDED.location,
  estimated_value     = EXCLUDED.estimated_value,
  currency            = EXCLUDED.currency,
  post_date           = EXCLUDED.post_date,
  due_date            = EXCLUDED.due_date,
  status              = EXCLUDED.status,
  service_lines       = EXCLUDED.service_lines,
  nigp_codes          = EXCLUDED.nigp_codes,
  naics_codes         = EXCLUDED.naics_codes,
  source_url          = EXCLUDED.source_url,
  documents_url       = EXCLUDED.documents_url,
  raw_payload         = EXCLUDED.raw_payload,
  normalized_at       = NOW(),
  updated_at          = NOW()
RETURNING id, fit_score;
SQL
```

Do NOT write to `search_vector` — the `opportunities_search_vector_trigger`
maintains it from `title` + `description` automatically.

### Logging a connector run into ingestion_logs

```bash
psql "$DATABASE_URL" -c "
  INSERT INTO ingestion_logs (
    source, run_at, status,
    records_found, records_inserted, records_updated,
    error_message, duration_ms
  ) VALUES (
    'bidbuy', NOW(), 'success',
    42, 12, 5,
    NULL, 8432
  );
"
```

Column reminder: `records_found` / `records_inserted` / `records_updated` /
`error_message`. NOT `records_scraped` / `records_new` / `error`.

### Task worker update

```bash
psql "$DATABASE_URL" -c "
  UPDATE tasks
     SET status = 'done', completed_at = NOW()
   WHERE id = '<task-uuid>';
"
```

On failure:
```bash
psql "$DATABASE_URL" -c "
  UPDATE tasks
     SET status = 'failed', error_message = 'connector timeout', completed_at = NOW()
   WHERE id = '<task-uuid>';
"
```

### Rules
- Always `ON CONFLICT` on inserts into `opportunities` (keyed on `(source, source_id)`)
- Always `RETURNING id` after writes so you can chain into scoring/alerts
- Wrap multi-statement operations in `BEGIN; ... COMMIT;`
- Never `DROP TABLE`, never `DELETE FROM opportunities` without explicit user instruction
- Never write to `search_vector` — it's trigger-maintained

## Postgres MCP — Schema Inspection Only

Use for: listing tables, checking column names, inspecting indexes.
Do NOT use for writes — the MCP server is read-only.

## Firecrawl MCP — Web Scraping

- Tool: `scrape` with `{ url, formats: ["markdown"] }`
- Use `onlyMainContent: true` for procurement listing pages
- Parse HTML tables from markdown output for bid records

For BidBuy pages the listing table renders as a markdown table:
`| Title | Agency | Value | Due Date | ID |`

## agent-send — WhatsApp Alerts

For HOT opportunity alerts and failure notifications:

```
agent-send to="+27XXXXXXXXX" message="🔥 HOT: IT Modernization — Illinois DOT — $2.1M — Due Apr 20"
```

Never rely on cron `--deliver` flag for WhatsApp — use `agent-send` in the
agent prompt/instructions (known bug #273).

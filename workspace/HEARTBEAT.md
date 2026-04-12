# CaptureIQ Heartbeat Checks

Runs every 30 minutes during business hours (06:00–22:00 SAST).
Return exactly `HEARTBEAT_OK` if all checks pass — no other output, no WhatsApp message.
If any check fails, send a WhatsApp alert via agent-send and return a brief summary.

---

tasks:

- name: source-freshness
  prompt: |
    Run this query via psql:
    SELECT source, MAX(run_at) as last_success
    FROM ingestion_logs
    WHERE status = 'success'
    GROUP BY source;

    Check if any source has last_success older than 4 hours ago AND current time is between 06:00 and 22:00 SAST.
    If yes: send WhatsApp alert via agent-send: "⚠️ CaptureIQ: {source} ingestion stale — last success {last_success}. Check gateway logs."
    If all sources are fresh, or it's outside business hours: return HEARTBEAT_OK.

- name: pipeline-throughput
  prompt: |
    Run this query via psql:
    SELECT COUNT(*) as new_count FROM opportunities WHERE created_at > NOW() - INTERVAL '6 hours';

    If new_count = 0 AND current time is between 10:00 and 20:00 SAST (peak hours):
    Send WhatsApp alert via agent-send: "⚠️ CaptureIQ: Zero new opportunities in 6 hours — pipeline may be stalled."
    Otherwise: return HEARTBEAT_OK.

- name: firecrawl-health
  prompt: |
    Run via exec: curl -s -o /dev/null -w "%{http_code}" "$FIRECRAWL_API_URL/health"

    If HTTP status is not 200:
    Send WhatsApp alert via agent-send: "⚠️ CaptureIQ: Firecrawl health check failed (status: {status}). Self-hosted instance may be down."
    If 200: return HEARTBEAT_OK.

- name: ingestion-error-rate
  prompt: |
    Run this query via psql:
    SELECT COUNT(*) as error_count FROM ingestion_logs WHERE status = 'error' AND run_at > NOW() - INTERVAL '1 hour';

    If error_count > 5:
    Send WhatsApp alert via agent-send: "⚠️ CaptureIQ: {error_count} ingestion errors in the last hour. Check ingestion_logs table."
    If error_count <= 5: return HEARTBEAT_OK.

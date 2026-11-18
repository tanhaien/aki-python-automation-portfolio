# Webhook JSON to CSV — fixed-scope buyer acceptance fixture

**Purpose:** give a prospective buyer a reproducible acceptance example before requesting a written quote. This is a synthetic demo, not evidence of prior paid work or a promise of production integration.

## Sample events (fictional; no personal data)

```json
{"event_id":"evt-001","kind":"purchase","amount_cents":1250,"occurred_at":"2026-11-17T00:00:00Z"}
{"event_id":"evt-002","kind":"refund","amount_cents":-250,"occurred_at":"2026-11-17T00:02:00Z"}
{"event_id":"evt-001","kind":"purchase","amount_cents":1250,"occurred_at":"2026-11-17T00:00:00Z"}
```

## Acceptance rules

- CSV columns must be exactly `event_id,kind,amount_cents,occurred_at` in that order.
- Deduplicate by `event_id`, keeping the first occurrence. This is a business rule agreed **for this sample only**, not universal.
- Preserve integer cents, including negatives; do not silently convert to currency or apply tax.
- Preserve the ISO-8601 UTC timestamps exactly. Reject malformed input with a clear error rather than silently drop it.
- Output is two data rows, in original arrival order; a trailing newline is allowed.

```csv
event_id,kind,amount_cents,occurred_at
evt-001,purchase,1250,2026-11-17T00:00:00Z
evt-002,refund,-250,2026-11-17T00:02:00Z
```

## Quote request (written-only)

Send three **redacted or synthetic** representative events, desired column names, dedupe/missing-field policy, approximate input volume, required delivery date and budget range through the platform's approved messaging or the [GitHub quote request form](https://github.com/tanhaien/aki-python-automation-portfolio/issues/new?template=service_quote.yml). Do not share production API keys, credentials, real personal data or payment details. The sample is illustrative and does not authorize work; final scope, fee, delivery time, and acceptance criteria must be agreed in writing. Work begins only after a platform-funded milestone, if applicable. AI-assisted code may be used with review and tests when the marketplace and buyer permit it.

**Not included:** live webhook hosting, SaaS uptime, data migration, sensitive-data processing, financial reconciliation, deployment or maintenance. No claims of sales, buyer replies, clicks or paid contracts are made by this document.

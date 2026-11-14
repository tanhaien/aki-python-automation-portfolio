# Webhook JSON → CSV: Troubleshooting Duplicate Rows, Missing Fields and Broken Exports

*Original practical checklist · Python 3.10+ · synthetic examples · no live webhook or third-party credentials*

**Search intent:** Why does my webhook CSV have duplicate rows? Why do some columns disappear? Why does Excel display timestamps or identifiers incorrectly? This guide helps diagnose those problems **before** paying for a custom integration.

## Symptom → cause → safe fix

| Symptom | Likely cause | First check | Safe approach |
| --- | --- | --- | --- |
| The same order appears twice | Sender retried a webhook after timeout | Compare provider event IDs, not arrival timestamps | Store stable event IDs; make retries idempotent |
| A column is empty | Field absent, renamed or nested | Compare event JSON keys against a versioned schema | Explicit field mapping and a documented missing-field policy |
| Two events share an ID but differ | Identity collision or conflicting replay | Compare normalized payloads, not just IDs | Reject and investigate; never silently overwrite |
| An identifier becomes `1.23E+12` in Excel | Spreadsheet auto-detected a long string as a number | Inspect the raw CSV with a text editor | Keep identifiers as strings; validate spreadsheet import settings |
| Export loses rows or is partially written | Process crash or simultaneous writers | Reproduce with a forced write failure and two workers | Use atomic replacement and a lock for local-file workloads; a database for multi-host workloads |
| A cell starts with `=`, `+`, `-` or `@` | Spreadsheet may interpret untrusted text as a formula | Check how the target spreadsheet imports CSV | Treat as CSV formula-injection risk; choose an explicit, tested import/escaping policy |

**Important:** A CSV file cannot force every spreadsheet to preserve string types. The appropriate import settings, a safer XLSX export with typed text cells, or an agreed formula-escaping convention may be necessary. Do not assume prepending an apostrophe is universally safe.

## Reproduce two common problems without external services

Save this as `diagnose_events.py` and run `python3 diagnose_events.py`:

```python
import json

events = [
    {"source": "demo", "event_id": "evt-101", "status": "paid"},
    {"source": "demo", "event_id": "evt-101", "status": "paid"},
    {"source": "demo", "event_id": "evt-101", "status": "refunded"},
    {"source": "demo", "event_id": "evt-102", "state": "paid"},
]

required = {"source", "event_id", "status"}
seen = {}

for event in events:
    missing = sorted(required - event.keys())
    if missing:
        print("SCHEMA_MISMATCH", event["event_id"], missing)
        continue
    identity = (event["source"], event["event_id"])
    canonical = json.dumps(event, sort_keys=True, separators=(",", ":"))
    if identity not in seen:
        seen[identity] = canonical
        print("NEW", event["event_id"])
    elif seen[identity] == canonical:
        print("RETRY", event["event_id"])
    else:
        print("CONFLICT", event["event_id"])
```

Expected output:

```text
NEW evt-101
RETRY evt-101
CONFLICT evt-101
SCHEMA_MISMATCH evt-102 ['status']
```

This is a **diagnostic snippet**, not a secure webhook server, durable ledger, production importer, refund-processing system, or financial reconciliation tool. In particular, an actual payment/refund lifecycle needs explicit provider-specific event types and reconciliation; it must not be treated as a conflicting replay merely because the same business order changed status.

## What to send when requesting a fixed-scope repair

Send only **invented or redacted** sample JSON, desired CSV column names, one example of a wrong output row, expected correct output, approximate daily volume, Python version and whether multiple workers write simultaneously. Do **not** post customer records, API keys, signed webhook headers, access tokens, or confidential code in public GitHub issues.

For a small written-only job, the initial scope can be **one schema, one local batch export, up to 10 columns, deterministic mapping and synthetic regression tests**. Live endpoint deployment, signature validation, high availability and large-scale reconciliation are separate projects; an estimate is not a contract or guaranteed price.

**Next steps:** [Run the original idempotent CSV demo](python-webhook-csv-deduplication.md) · [Use the fixed-scope buyer checklist](webhook-to-csv-fixed-scope-quote-checklist.md) · [Request a written quote (public issue; no private data)](https://github.com/tanhaien/aki-python-automation-portfolio/issues/new?template=service_quote.yml).

*Original educational content. AI assistance may be used during development with human review; no previous paid customer delivery, revenue, or performance outcome is implied.*

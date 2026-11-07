# Prevent Duplicate Webhook CSV Rows with Python Idempotency

*Practical offline tutorial · Python 3.10+ · synthetic data only*

Webhook providers can retry an event after a timeout. If a handler appends every delivery to a CSV, retries may become duplicate rows. This walkthrough demonstrates a local receipt-import pattern that distinguishes an exact replay from a new event and refuses conflicting replays.

> **Scope:** This repository's [Webhook-to-CSV demo](../demo/webhook_csv/README.md) processes saved JSON events through a CLI. It does **not** expose a webhook HTTP server or verify provider signatures. It is educational and not production accounting software.

## Three event outcomes

| Event | Result | CSV effect |
| --- | --- | --- |
| New `source + event_id` | `inserted` | One new row |
| Same identity and same normalized payload | `duplicate` | No new row |
| Same identity but changed payload | `ConflictError` | Reject; preserve existing rows |

The importer computes a stable SHA-256 identity from the tuple `[source, event_id]`. It independently hashes the normalized payload to detect a replay that changes its contents. Strict schema validation rejects missing/unknown properties, unsafe values, duplicate JSON keys and invalid timestamps.

## Reproduce locally

```bash
git clone https://github.com/tanhaien/aki-python-automation-portfolio.git
cd aki-python-automation-portfolio/demo/webhook_csv

python3 -m unittest discover -s tests -v
python3 -m webhook_csv --input samples/event_001.json --output ./output/receipts.csv
python3 -m webhook_csv --input samples/event_001.json --output ./output/receipts.csv
python3 -m webhook_csv --input samples/event_002.json --output ./output/receipts.csv
```

Expected status sequence: **inserted → duplicate → inserted**. The final CSV has two distinct rows. The unit suite has **12 deterministic cases** covering validation, idempotency, conflicts, failed-write preservation, and participating concurrent writers.

All example IDs are invented; no credentials or personal/customer data are used.

## How does the CSV stay consistent?

A naive append does not guard against concurrent writers. The sample validates the existing CSV, acquires a participating local lock, writes a whole-file snapshot to a temporary file, flushes it, and replaces the target using `os.replace`. This keeps the old file intact if the replacement fails, subject to the local filesystem's guarantees.

It is intentionally a **low-volume local file design**. It rewrites the CSV rather than providing a database transaction. The existing-ledger size cap is 8 MiB and each JSON input is capped at 64 KiB.

## What you must add for real integrations

1. Authenticate the HTTPS request and validate the sender's signed webhook payload *before* importing JSON.
2. Define provider-specific stable event identity and replay windows.
3. Plan timeout, retry, failure alerting, backups and access controls.
4. Prefer SQLite/PostgreSQL for large volumes, multi-worker cloud deployments, or robust reconciliation.
5. Do not mistake this receipt CSV for an audit-proof ledger or financial accounting platform.

For full limitations, review [the demo's known limitations](../demo/webhook_csv/docs/KNOWN_LIMITATIONS.md). Avoid copying this design verbatim into production without reviewing your own threat model.

## Video + small scoped assistance

A 32-second original terminal demonstration has been recorded and prepared as a vertical video, but a public YouTube link is **not yet available**. No paid clients, endorsements, buyer orders or verified ROI are claimed.

For small Python, CSV or API automation scopes, see [the portfolio service menu](../README.md). Written-only work can be considered after defining input/output examples and agreeing on an appropriate funded milestone. Do not put credentials or private files in public GitHub issues.

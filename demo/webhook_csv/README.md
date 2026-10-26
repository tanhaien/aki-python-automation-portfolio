# Webhook-to-CSV Receipt & Deduplication Utility

**Evaluation sample · v0.1.0 · 2026-10-26 · Python 3.10+ stdlib only**

A small, reusable Python module that accepts a saved JSON webhook event, validates a strict v1 receipt schema, computes deterministic SHA-256 identifiers, and transactionally **adds** one row to a local CSV receipt ledger. Replays do not create duplicate rows. No service credentials, customer exports, external APIs, databases, packages, or network calls are required.

## Quick start

From this folder:

```bash
python3 -m unittest discover -s tests -v
python3 -m webhook_csv --input samples/event_001.json --output /tmp/osmium-demo/receipts.csv
python3 -m webhook_csv --input samples/event_001.json --output /tmp/osmium-demo/receipts.csv
python3 -m webhook_csv --input samples/event_002.json --output /tmp/osmium-demo/receipts.csv
```

Expected CLI status values: `inserted`, `duplicate`, `inserted`. Review the resulting `receipts.csv` with a spreadsheet or text editor. On Windows, substitute a writable local CSV output path for `/tmp`.

### Programmatic use

```python
from webhook_csv import decode_json, ingest

with open("samples/event_001.json", "rb") as f:
    result = ingest(decode_json(f.read()), "./output/receipts.csv")
print(result["status"])  # inserted or duplicate
```

The caller is responsible for HTTP authentication, validating webhook signatures and configuring retry behavior before handing a verified JSON payload to `ingest`. This repository **does not expose an HTTP server**. This boundary is intentional for a code-reviewable, no-credentials sample.

## Strict receipt schema (v1)

All eight fields are required; unknown fields and JSON duplicate properties are rejected.

| Field | Type | Validation |
|---|---|---|
| `schema_version` | integer | exact value `1` |
| `event_id` | string | 1–128 chars, safe identifier; cannot start with spreadsheet formula character |
| `event_type` | string | 1–80 chars, starts with letter; e.g. `receipt.created` |
| `occurred_at` | string | RFC3339 including `Z` or `+HH:MM`; normalized to UTC |
| `source` | string | 1–128 safe identifier chars, scoped with `event_id` for idempotency |
| `amount_minor` | integer | integer 0…9e15; no booleans/floats; units such as cents |
| `currency` | string | three uppercase ASCII letters, e.g. `USD` (syntax only, not ISO membership verification) |
| `customer_ref` | string | synthetic reference identifier; **not** PII/name/email |

Example file: `samples/event_001.json`. The two examples contain **invented identifiers** and **no real customer data**.

### Idempotency and write semantics

- `idempotency_hash = SHA256(JSON([source, event_id]))`, using fixed separators and UTF-8.
- `payload_sha256 = SHA256(canonical JSON of the normalized event)`, sorted keys, fixed separators, normalized UTC timestamp.
- Same identity + same payload = `duplicate` with no write. Same identity + different payload = `ConflictError` (fail closed).
- **Atomic append semantics are implemented with read-modify-write + `os.replace`, under a cross-process lock file, NOT with an in-place `O_APPEND` syscall.** The existing CSV is not partially modified if a new snapshot write fails. Writes are serialized among callers using this package.
- Temporary file is created in the target directory, `fsync`ed, then atomically replaced. The lock file remains on disk. This is a low-volume local utility, not a high-throughput database.
- Existing ledgers have an 8 MiB size cap to limit rewriting cost. Input JSON is limited to 64 KiB. Unexpected CSV schema, malformed row or checksum format causes a refusal to append.

### Exit codes

- `0`: inserted or duplicate
- `2`: invalid JSON/schema, IO/storage error
- `3`: same identity with conflicting payload

## Evidence and review

- `tests/test_receipts.py`: **exactly 12 deterministic `unittest` cases**. Temporary directories and synthetic inputs only.
- `evidence/test_output.txt`: local command output, Python version, exit status.
- `evidence/cli_output.txt`: sample insertion and replay transcript.
- `docs/HANDOFF.md`: review checklist and acceptance criteria.
- `docs/KNOWN_LIMITATIONS.md`: non-goals, threat model, and scaling limits.

## Privacy and security

Never send secrets, live webhook signing keys, private client payloads, account information, or confidential data with this sample. Incoming schema intentionally rejects arbitrary payload fields. The CLI prints only status and idempotency hash; no raw request bodies. CSV files can contain business information if the schema is extended in the future; use access controls and retention policies appropriate to deployment.

**Rights:** Submitted only as an independent evaluation sample. Authorship/IP and terms of any marketplace listing or commercial license are to be agreed in writing; no prior paid client work is claimed.

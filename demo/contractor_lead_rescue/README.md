# Contractor Lead Rescue — Offline Demonstration

**Buyer problem:** Home-service contractors receive inquiry emails from lead marketplaces, miss callbacks, duplicate entries and do not know which owner should contact whom.

**What this MVP actually does:** Given user-authorized JSONL exports, it records leads locally in SQLite with deterministic (source, external_id) deduplication, detects conflicting replays, schedules a follow-up queue, tracks status changes and audit events, and exports a spreadsheet-safe CSV. It runs entirely offline, on synthetic data, without paid APIs.

**What this MVP does NOT do:** No direct integration with Angi, Thumbtack, Networx, Make.com, Gmail, WhatsApp Business Cloud API, SMS, AI, voice transcription, external scraping or actual reminders dispatched to customers. Those are potential separately scoped integrations requiring customer authorization, credentials, pricing and vendor-policy checks. Never claim these features exist.

## Reproduce in ~30 seconds
Python 3.10+ only, no dependencies:

    cd demos/contractor-lead-rescue
    python3 -m unittest -v test_lead_rescue.py
    ./demo.sh

## Commands

    python3 lead_rescue.py --db myleads.sqlite ingest fixtures/leads.jsonl
    python3 lead_rescue.py --db myleads.sqlite reminders --date 2026-11-02
    python3 lead_rescue.py --db myleads.sqlite update --source Angi --id synthetic-101 --status contacted --follow-up 2026-11-05
    python3 lead_rescue.py --db myleads.sqlite export > leads.csv

Reminders ONLY prints an internal work queue; nothing is sent. Dates are calendar dates selected by the operator, not inferred from computer time zone. CSV export escapes common spreadsheet formulas. Keep customer data on a secured device, do not commit actual lead data, and obtain permission for any third-party integrations. SQLite here is a single-device prototype, not a multi-user SaaS or CRM.

## Pilot acceptance checklist
- Owner identifies 2 lead sources, provides redacted samples, and authorizes data handling.
- Agree source-specific unique ID, duplicate semantics, owner assignment and time-zone.
- 10 test leads imported exactly once; conflicting replay visibly fails.
- Partner can view due/overdue follow-ups and reschedule them.
- Check output against source and export CSV.
- Only after approval: specify integration triggers, credentials handling, auth, retry, logging, WhatsApp templates / sender permissions, and manual override.

**Suggested scope-based pricing (hypotheses, not confirmed sales):**
- $19 downloadable workflow template + documentation (future product, not for sale until complete).
- $199 setup of approved source file → lead sheet / reminders (requires scope confirmation).
- $300+ third-party integrations or voice via separate quote. External API charges excluded.

All names, contacts, dates and marketplace leads in fixtures are invented.

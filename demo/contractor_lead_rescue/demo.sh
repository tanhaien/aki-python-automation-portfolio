#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
DB="$(mktemp /tmp/lead-rescue-demo.XXXXXX.sqlite)"
trap 'rm -f "$DB"' EXIT
echo '--- Import ---'
python3 lead_rescue.py --db "$DB" ingest fixtures/leads.jsonl
echo '--- Replay should be skipped ---'
python3 lead_rescue.py --db "$DB" ingest fixtures/leads.jsonl
echo '--- Follow-ups due 2026-11-02 ---'
python3 lead_rescue.py --db "$DB" reminders --date 2026-11-02
echo '--- Mark one contacted and reschedule ---'
python3 lead_rescue.py --db "$DB" update --source Angi --id synthetic-101 --status contacted --follow-up 2026-11-05 --note 'Customer callback scheduled'
echo '--- Updated follow-ups due 2026-11-02 ---'
python3 lead_rescue.py --db "$DB" reminders --date 2026-11-02
echo '--- Export preview ---'
python3 lead_rescue.py --db "$DB" export

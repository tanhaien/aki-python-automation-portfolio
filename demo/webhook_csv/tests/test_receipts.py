import csv
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from webhook_csv import ConflictError, ValidationError, decode_json, ingest, normalize_event

BASE = {
    "schema_version": 1,
    "event_id": "evt_synthetic_001",
    "event_type": "receipt.created",
    "occurred_at": "2026-10-26T08:20:00Z",
    "source": "synthetic_gateway",
    "amount_minor": 1299,
    "currency": "USD",
    "customer_ref": "cust_demo_001",
}


class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name) / "receipts.csv"

    def rows(self):
        with self.output.open(encoding="utf-8", newline="") as fp:
            return list(csv.DictReader(fp))

    def test_01_insert_creates_csv_receipt(self):
        self.assertEqual(ingest(BASE, self.output)["status"], "inserted")
        self.assertEqual(len(self.rows()), 1)
        self.assertEqual(self.rows()[0]["amount_minor"], "1299")

    def test_02_replay_same_event_is_noop(self):
        self.assertEqual(ingest(BASE, self.output)["status"], "inserted")
        self.assertEqual(ingest(BASE, self.output)["status"], "duplicate")
        self.assertEqual(len(self.rows()), 1)

    def test_03_same_identity_changed_payload_conflicts(self):
        ingest(BASE, self.output)
        with self.assertRaises(ConflictError):
            ingest({**BASE, "amount_minor": 42}, self.output)
        self.assertEqual(len(self.rows()), 1)

    def test_04_distinct_event_id_adds_second_row(self):
        ingest(BASE, self.output)
        ingest({**BASE, "event_id": "evt_synthetic_002"}, self.output)
        self.assertEqual(len(self.rows()), 2)

    def test_05_same_event_id_from_other_source_is_distinct(self):
        ingest(BASE, self.output)
        ingest({**BASE, "source": "other_gateway"}, self.output)
        self.assertEqual(len(self.rows()), 2)

    def test_06_json_key_order_does_not_change_identity(self):
        ingest(BASE, self.output)
        reordered = dict(reversed(list(BASE.items())))
        self.assertEqual(ingest(reordered, self.output)["status"], "duplicate")

    def test_07_equivalent_timezone_is_deduplicated(self):
        ingest(BASE, self.output)
        other_tz = {**BASE, "occurred_at": "2026-10-26T15:20:00+07:00"}
        self.assertEqual(ingest(other_tz, self.output)["status"], "duplicate")

    def test_08_schema_rejects_missing_and_extra_fields(self):
        for event in ({k: v for k, v in BASE.items() if k != "currency"},
                      {**BASE, "api_token": "DO_NOT_LOG"}):
            with self.subTest(event=event):
                with self.assertRaises(ValidationError):
                    normalize_event(event)

    def test_09_rejects_bool_negative_amount_and_bad_date(self):
        for changes in ({"amount_minor": True}, {"amount_minor": -1},
                        {"occurred_at": "2026-10-26T08:20:00"},
                        {"occurred_at": "2026-02-30T10:00:00Z"}):
            with self.subTest(changes=changes):
                with self.assertRaises(ValidationError):
                    normalize_event({**BASE, **changes})

    def test_10_rejects_formula_injection_and_duplicate_json_keys(self):
        with self.assertRaises(ValidationError):
            normalize_event({**BASE, "customer_ref": "=HYPERLINK(\"https://evil\")"})
        with self.assertRaises(ValidationError):
            decode_json(b'{"event_id":"x","event_id":"y"}')

    def test_11_failed_replace_preserves_existing_csv(self):
        ingest(BASE, self.output)
        before = self.output.read_bytes()
        with patch("webhook_csv.core.os.replace", side_effect=OSError("simulated failure")):
            with self.assertRaises(OSError):
                ingest({**BASE, "event_id": "evt_synthetic_002"}, self.output)
        self.assertEqual(before, self.output.read_bytes())
        self.assertEqual(list(Path(self.temp.name).glob(".receipts-*.tmp")), [])

    def test_12_concurrent_replays_commit_once(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            statuses = list(pool.map(lambda _: ingest(dict(BASE), self.output)["status"], range(8)))
        self.assertEqual(statuses.count("inserted"), 1)
        self.assertEqual(statuses.count("duplicate"), 7)
        self.assertEqual(len(self.rows()), 1)


if __name__ == "__main__":
    unittest.main()

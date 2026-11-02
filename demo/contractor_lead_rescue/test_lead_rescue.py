import csv
import io
import tempfile
import unittest
from pathlib import Path
from lead_rescue import connect, ingest, due, update, export_csv

BASE = dict(source="Angi",external_id="lead-1",customer="Alex Example",
            contact="alex@example.invalid",job_type="Repair",owner="Pat",
            follow_up="2026-11-02")
class LeadRescueTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.conn=connect(str(Path(self.tmp.name)/"leads.sqlite"))
    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()
    def test_import(self):
        self.assertEqual(ingest(self.conn,[BASE]),(1,0))
    def test_idempotency(self):
        ingest(self.conn,[BASE])
        self.assertEqual(ingest(self.conn,[BASE]),(0,1))
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0],1)
    def test_conflict_rejected(self):
        ingest(self.conn,[BASE])
        with self.assertRaisesRegex(ValueError,"Conflicting replay"):
            ingest(self.conn,[dict(BASE,contact="different@example.invalid")])
    def test_transactional_batch(self):
        ingest(self.conn,[BASE])
        with self.assertRaises(ValueError):
            ingest(self.conn,[dict(BASE,external_id="lead-2"),dict(BASE,customer="different")])
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0],1)
    def test_bad_date(self):
        with self.assertRaises(ValueError):
            ingest(self.conn,[dict(BASE,follow_up="2026-02-30")])
    def test_bad_status(self):
        with self.assertRaises(ValueError):
            ingest(self.conn,[dict(BASE,status="paid")])
    def test_missing_value(self):
        with self.assertRaises(ValueError):
            ingest(self.conn,[dict(BASE,owner="")])
    def test_due_inclusive(self):
        ingest(self.conn,[BASE])
        self.assertEqual(len(due(self.conn,"2026-11-01")),0)
        self.assertEqual(len(due(self.conn,"2026-11-02")),1)
        self.assertEqual(len(due(self.conn,"2026-11-03")),1)
    def test_owner_filter(self):
        ingest(self.conn,[BASE])
        self.assertEqual(len(due(self.conn,"2026-11-02","Sam")),0)
        self.assertEqual(len(due(self.conn,"2026-11-02","Pat")),1)
    def test_closed_excluded(self):
        ingest(self.conn,[BASE])
        update(self.conn,"Angi","lead-1","won",None,None)
        self.assertEqual(len(due(self.conn,"2026-11-10")),0)
    def test_reschedule(self):
        ingest(self.conn,[BASE])
        self.assertTrue(update(self.conn,"Angi","lead-1","contacted","2026-11-05","Call again"))
        self.assertEqual(len(due(self.conn,"2026-11-02")),0)
        self.assertEqual(len(due(self.conn,"2026-11-05")),1)
    def test_unknown_lead(self):
        self.assertFalse(update(self.conn,"Angi","missing","won",None,None))
    def test_audit(self):
        ingest(self.conn,[BASE])
        update(self.conn,"Angi","lead-1","quoted",None,None)
        events=list(self.conn.execute("SELECT action FROM events ORDER BY id"))
        self.assertEqual([e[0] for e in events],["ingest","update"])
    def test_formula_injection_escape(self):
        ingest(self.conn,[dict(BASE,customer="=HYPERLINK('bad')",owner="@evil")])
        data=list(csv.DictReader(io.StringIO(export_csv(self.conn))))[0]
        self.assertTrue(data["customer"].startswith("'="))
        self.assertTrue(data["owner"].startswith("'@"))
    def test_invalid_followup_on_update(self):
        ingest(self.conn,[BASE])
        with self.assertRaises(ValueError):
            update(self.conn,"Angi","lead-1",None,"tomorrow",None)
if __name__=="__main__":
    unittest.main()

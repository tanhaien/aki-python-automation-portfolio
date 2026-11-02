#!/usr/bin/env python3
"""Local-only, deterministic contractor lead tracker. No auto outreach."""
from __future__ import annotations
import argparse
import csv
import io
import json
import sqlite3
import sys
from datetime import date
from pathlib import Path

STATES = {"new", "contacted", "quoted", "won", "lost"}
CLOSED = {"won", "lost"}
FIELDS = ("source", "external_id", "customer", "contact", "job_type", "owner", "follow_up", "status", "note")
SCHEMA = """
CREATE TABLE IF NOT EXISTS leads (
  source TEXT NOT NULL,
  external_id TEXT NOT NULL,
  customer TEXT NOT NULL,
  contact TEXT NOT NULL,
  job_type TEXT NOT NULL,
  owner TEXT NOT NULL,
  follow_up TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'new',
  note TEXT NOT NULL DEFAULT '',
  PRIMARY KEY(source, external_id)
);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY,
  source TEXT NOT NULL,
  external_id TEXT NOT NULL,
  action TEXT NOT NULL,
  detail TEXT NOT NULL,
  at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""
def valid_date(value: str) -> str:
    if date.fromisoformat(value).isoformat() != value:
        raise ValueError("Date must be ISO YYYY-MM-DD")
    return value

def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn

def validate(item: dict) -> dict:
    if not isinstance(item, dict):
        raise ValueError("Each lead must be a JSON object")
    required = ("source", "external_id", "customer", "contact", "job_type", "owner", "follow_up")
    if any(not isinstance(item.get(k), str) or not item[k].strip() for k in required):
        raise ValueError("Missing or empty required lead field")
    out = {k: item[k].strip() for k in required}
    if any(len(v) > 300 for v in out.values()):
        raise ValueError("Field exceeds 300 characters")
    out["follow_up"] = valid_date(out["follow_up"])
    out["status"] = item.get("status", "new")
    if out["status"] not in STATES:
        raise ValueError("Invalid status")
    out["note"] = item.get("note", "")
    if not isinstance(out["note"], str) or len(out["note"]) > 2000:
        raise ValueError("Invalid note")
    return out

def ingest(conn: sqlite3.Connection, entries: list[dict]) -> tuple[int, int]:
    """All-or-nothing import. Duplicate same record ignored; conflicting replay rejected."""
    count, skipped = 0, 0
    with conn:
        for raw in entries:
            item = validate(raw)
            prior = conn.execute("SELECT * FROM leads WHERE source=? AND external_id=?",
                (item["source"], item["external_id"])).fetchone()
            if prior:
                # Mutable workflow fields are controlled by update, not re-ingestion.
                immutable = ("customer", "contact", "job_type")
                if any(prior[k] != item[k] for k in immutable):
                    raise ValueError(f"Conflicting replay: {item['source']}/{item['external_id']}")
                skipped += 1
                continue
            conn.execute("""INSERT INTO leads
                (source,external_id,customer,contact,job_type,owner,follow_up,status,note)
                VALUES (:source,:external_id,:customer,:contact,:job_type,:owner,:follow_up,:status,:note)""", item)
            conn.execute("INSERT INTO events(source,external_id,action,detail) VALUES(?,?,?,?)",
                (item["source"],item["external_id"],"ingest","new lead"))
            count += 1
    return count, skipped

def due(conn: sqlite3.Connection, today: str, owner: str|None=None) -> list[sqlite3.Row]:
    valid_date(today)
    query = "SELECT * FROM leads WHERE follow_up<=? AND status NOT IN ('won','lost')"
    args = [today]
    if owner:
        query += " AND owner=?"
        args.append(owner)
    return conn.execute(query+" ORDER BY owner, follow_up, source, external_id", args).fetchall()

def update(conn: sqlite3.Connection, source: str, lead_id: str, status: str|None,
           follow_up: str|None, note: str|None) -> bool:
    if status is not None and status not in STATES:
        raise ValueError("Invalid status")
    if follow_up is not None:
        valid_date(follow_up)
    if note is not None and len(note)>2000:
        raise ValueError("Note exceeds limit")
    with conn:
        prev = conn.execute("SELECT * FROM leads WHERE source=? AND external_id=?",
                            (source, lead_id)).fetchone()
        if prev is None:
            return False
        if status is None and follow_up is None and note is None:
            raise ValueError("No changes")
        changes = {"status": status or prev["status"],
                   "follow_up": follow_up or prev["follow_up"],
                   "note": note if note is not None else prev["note"]}
        conn.execute("UPDATE leads SET status=:status, follow_up=:follow_up, note=:note "
                     "WHERE source=:source AND external_id=:external_id",
                     dict(changes, source=source, external_id=lead_id))
        conn.execute("INSERT INTO events(source,external_id,action,detail) VALUES(?,?,?,?)",
                     (source,lead_id,"update",json.dumps(changes,sort_keys=True)))
    return True

def csv_safe(value: str) -> str:
    """Avoid Excel/Sheets formula execution when exporting user-supplied cells."""
    if value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n")):
        return "'"+value
    return value

def export_csv(conn: sqlite3.Connection) -> str:
    dest = io.StringIO()
    writer = csv.writer(dest)
    writer.writerow(FIELDS)
    for row in conn.execute("SELECT * FROM leads ORDER BY source,external_id"):
        writer.writerow([csv_safe(str(row[k])) for k in FIELDS])
    return dest.getvalue()

def main(argv=None):
    p=argparse.ArgumentParser(description="Contractor Lead Rescue: offline proof of concept")
    p.add_argument("--db",default="lead_rescue.sqlite")
    sub=p.add_subparsers(dest="action",required=True)
    inp=sub.add_parser("ingest"); inp.add_argument("jsonl")
    remind=sub.add_parser("reminders"); remind.add_argument("--date",required=True); remind.add_argument("--owner")
    upd=sub.add_parser("update"); upd.add_argument("--source",required=True); upd.add_argument("--id",required=True)
    upd.add_argument("--status",choices=sorted(STATES)); upd.add_argument("--follow-up"); upd.add_argument("--note")
    sub.add_parser("export")
    sub.add_parser("stats")
    args=p.parse_args(argv)
    try:
        with connect(args.db) as db:
            if args.action=="ingest":
                lines=Path(args.jsonl).read_text(encoding="utf8").splitlines()
                entries=[json.loads(line) for line in lines if line.strip()]
                added,ignored=ingest(db,entries)
                print(f"Imported {added}; safely skipped {ignored} duplicate(s).")
            elif args.action=="reminders":
                records=due(db,args.date,args.owner)
                print(f"FOLLOW-UP QUEUE {args.date} ({len(records)} due/overdue)")
                for r in records:
                    print(f"  {r['owner']} | {r['follow_up']} | {r['source']}/{r['external_id']} | "
                          f"{r['customer']} | {r['job_type']} | {r['status']}")
                print("Preview only: no WhatsApp, SMS or email was sent.")
            elif args.action=="update":
                if not update(db,args.source,args.id,args.status,args.follow_up,args.note):
                    raise ValueError("Lead not found")
                print("Updated lead and logged audit event.")
            elif args.action=="export":
                sys.stdout.write(export_csv(db))
            elif args.action=="stats":
                for r in db.execute("SELECT status, COUNT(*) n FROM leads GROUP BY status ORDER BY status"):
                    print(f"{r['status']}: {r['n']}")
    except (ValueError,sqlite3.Error, OSError,json.JSONDecodeError) as exc:
        p.exit(2,f"Error: {exc}\n")

if __name__=="__main__":
    main()

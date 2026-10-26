"""Deterministic webhook JSON -> CSV receipt ingestion. Python stdlib only.

The on-disk update uses atomic replacement under a cross-process advisory lock.
This gives all-or-nothing CSV row visibility; it is NOT an in-place append syscall.
"""

from __future__ import annotations

import contextlib
import csv
import hashlib
import io
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

FIELDS = (
    "schema_version", "event_id", "event_type", "occurred_at",
    "source", "amount_minor", "currency", "customer_ref",
)
CSV_COLUMNS = ("idempotency_hash", "payload_sha256", *FIELDS)
MAX_JSON_BYTES = 64 * 1024
MAX_CSV_BYTES = 8 * 1024 * 1024
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_EVENT_TYPE = re.compile(r"^[A-Za-z][A-Za-z0-9._-]{0,79}$")
_CURRENCY = re.compile(r"^[A-Z]{3}$")
_TS = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$")


class ValidationError(ValueError):
    """Input is malformed or outside the declared example schema."""


class ConflictError(ValueError):
    """The same source+event_id was replayed with different content."""


class StorageError(RuntimeError):
    """On-disk CSV is too large, invalid or unsafe to update."""


def _object_no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ValidationError(f"duplicate JSON property: {key}")
        out[key] = value
    return out


def decode_json(raw: bytes) -> dict[str, Any]:
    """Parse bounded UTF-8 JSON while rejecting duplicate properties and NaN."""
    if len(raw) > MAX_JSON_BYTES:
        raise ValidationError(f"JSON exceeds {MAX_JSON_BYTES} byte limit")
    try:
        obj = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_object_no_duplicate_keys,
            parse_constant=lambda constant: (_ for _ in ()).throw(
                ValidationError(f"non-JSON number: {constant}")
            ),
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValidationError("invalid UTF-8 JSON") from exc
    if not isinstance(obj, dict):
        raise ValidationError("top-level JSON must be an object")
    return obj


def normalize_event(event: dict[str, Any]) -> dict[str, Any]:
    """Validate v1 schema exactly and normalize timestamps to UTC."""
    if not isinstance(event, dict):
        raise ValidationError("event must be an object")
    missing = sorted(set(FIELDS) - set(event))
    extra = sorted(set(event) - set(FIELDS))
    if missing or extra:
        raise ValidationError(f"schema fields mismatch: missing={missing}, extra={extra}")
    if type(event["schema_version"]) is not int or event["schema_version"] != 1:
        raise ValidationError("schema_version must be integer 1")
    for field in ("event_id", "source", "customer_ref"):
        val = event[field]
        if not isinstance(val, str) or not _ID.fullmatch(val):
            raise ValidationError(f"{field} must be 1-128 safe identifier characters")
    val = event["event_type"]
    if not isinstance(val, str) or not _EVENT_TYPE.fullmatch(val):
        raise ValidationError("invalid event_type")
    cur = event["currency"]
    if not isinstance(cur, str) or not _CURRENCY.fullmatch(cur):
        raise ValidationError("currency must be 3 uppercase ISO-like letters")
    amount = event["amount_minor"]
    if type(amount) is not int or not 0 <= amount <= 9_000_000_000_000_000:
        raise ValidationError("amount_minor must be a nonnegative bounded integer")
    stamp = event["occurred_at"]
    if not isinstance(stamp, str) or not _TS.fullmatch(stamp):
        raise ValidationError("occurred_at must be RFC3339 with timezone")
    try:
        moment = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        moment = moment.astimezone(timezone.utc)
    except ValueError as exc:
        raise ValidationError("invalid occurred_at date") from exc
    normalized = dict(event)
    normalized["occurred_at"] = moment.isoformat(timespec="microseconds").replace("+00:00", "Z")
    return normalized


def event_hashes(normalized: dict[str, Any]) -> tuple[str, str]:
    """Stable (source,event_id) idempotency key + content checksum."""
    identity = json.dumps([normalized["source"], normalized["event_id"]],
                          ensure_ascii=False, separators=(",", ":"))
    body = json.dumps(normalized, ensure_ascii=False,
                      sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(identity.encode("utf-8")).hexdigest(), hashlib.sha256(body.encode("utf-8")).hexdigest()


@contextlib.contextmanager
def _file_lock(lock_path: Path) -> Iterator[None]:
    """Advisory exclusive lock. All writers must use this utility."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        if os.name == "nt":
            import msvcrt
            if os.fstat(fd).st_size == 0:
                os.write(fd, b"\x00")
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == "nt":
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def _read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    if path.stat().st_size > MAX_CSV_BYTES:
        raise StorageError("CSV exceeds snapshot size limit")
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        if tuple(reader.fieldnames or ()) != CSV_COLUMNS:
            raise StorageError("CSV schema/header mismatch; refusing update")
        rows = list(reader)
    for row in rows:
        if None in row or None in row.values():
            raise StorageError("malformed CSV row; refusing update")
        for key in ("idempotency_hash", "payload_sha256"):
            value = row[key]
            if len(value) != 64 or not re.fullmatch(r"[0-9a-f]{64}", value):
                raise StorageError("malformed CSV receipt checksum")
    return rows


def _replace_csv_atomically(path: Path, rows: list[dict[str, str]]) -> None:
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="", delete=False,
            prefix=".receipts-", suffix=".tmp", dir=path.parent,
        ) as fh:
            tmp_path = Path(fh.name)
            writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, path)  # same-filesystem, atomic visibility
        if os.name != "nt":
            try:
                fd = os.open(path.parent, os.O_RDONLY)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
            except OSError:
                pass  # network filesystems/OS may not support directory fsync
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)


def ingest(event: dict[str, Any], output_path: str | Path) -> dict[str, str]:
    """Commit one validated receipt; idempotent across independent processes.

    Returns inserted/duplicate result. Raises ConflictError for event-id reuse
    with different contents. Never writes the raw JSON or credentials to disk.
    """
    normalized = normalize_event(event)
    key_hash, payload_hash = event_hashes(normalized)
    path = Path(output_path).expanduser().absolute()
    path.parent.mkdir(parents=True, exist_ok=True)
    with _file_lock(path.with_name(path.name + ".lock")):
        rows = _read_rows(path)
        for row in rows:
            if row["idempotency_hash"] == key_hash:
                if row["payload_sha256"] != payload_hash:
                    raise ConflictError("source + event_id already committed with different data")
                return {"status": "duplicate", "idempotency_hash": key_hash}
        new = {"idempotency_hash": key_hash, "payload_sha256": payload_hash,
               **normalized}
        rows.append({col: str(new[col]) for col in CSV_COLUMNS})
        _replace_csv_atomically(path, rows)
    return {"status": "inserted", "idempotency_hash": key_hash}

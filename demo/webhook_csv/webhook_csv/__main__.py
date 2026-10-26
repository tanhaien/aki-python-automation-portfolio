"""Command-line adapter for validated, saved webhook JSON events."""
import argparse
import json
import sys
from pathlib import Path
from .core import ConflictError, StorageError, ValidationError, decode_json, ingest


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Import one saved webhook JSON event into atomic CSV receipts")
    parser.add_argument("--input", required=True, help="UTF-8 JSON event file, or '-' for stdin")
    parser.add_argument("--output", required=True, help="CSV receipt destination")
    args = parser.parse_args(argv)
    try:
        if args.input == "-":
            raw = sys.stdin.buffer.read(65_537)
        else:
            with Path(args.input).open("rb") as fp:
                raw = fp.read(65_537)
        result = ingest(decode_json(raw), args.output)
    except (ValidationError, ConflictError, StorageError, OSError) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 3 if isinstance(exc, ConflictError) else 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

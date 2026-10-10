"""Local deterministic CSV cleanup. No network or third-party dependencies."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path


def _clean_header(value: str) -> str:
    return "_".join(value.strip().casefold().split())


def normalize_rows(rows: list[dict[str, str]], *, deduplicate: bool = True) -> list[dict[str, str]]:
    """Trim cells, normalize header keys, drop wholly empty rows, and dedupe.

    The caller is responsible for supplying non-conflicting normalized headers.
    """
    seen: set[tuple[tuple[str, str], ...]] = set()
    output: list[dict[str, str]] = []
    for row in rows:
        clean: dict[str, str] = {}
        for key, value in row.items():
            if key is None:
                raise ValueError("CSV row has more cells than its header")
            new_key = _clean_header(key)
            if not new_key:
                raise ValueError("empty header")
            if new_key in clean:
                raise ValueError("header collision after normalization")
            clean[new_key] = str(value or "").strip()
        if not any(clean.values()):
            continue
        signature = tuple(sorted(clean.items()))
        if deduplicate and signature in seen:
            continue
        seen.add(signature)
        output.append(clean)
    return output


def clean_file(source: Path, target: Path, *, deduplicate: bool = True) -> int:
    """Normalize a UTF-8 CSV into another path without changing the input."""
    if source.resolve() == target.resolve():
        raise ValueError("source and output must differ")
    with source.open("r", newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames:
            raise ValueError("CSV must contain a header")
        header = [_clean_header(h) for h in reader.fieldnames]
        if len(header) != len(set(header)) or not all(header):
            raise ValueError("duplicate or empty normalized headers")
        result = normalize_rows(list(reader), deduplicate=deduplicate)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=header, extrasaction="raise")
        writer.writeheader()
        writer.writerows(result)
    return len(result)


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize CSV data locally")
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--keep-duplicates", action="store_true")
    args = parser.parse_args()
    written = clean_file(args.source, args.output, deduplicate=not args.keep_duplicates)
    print(f"Output rows: {written}")


if __name__ == "__main__":
    main()

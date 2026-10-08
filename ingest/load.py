"""Build the DuckDB store from parsed sanctions records.

Two tables:
  entities  -- one row per sanctioned party (full evidence, lists stored as JSON)
  names     -- one row per name variant (primary + aliases), carrying the
               normalized match key and the strong/weak quality flag

The matcher runs over ``names.name_norm`` and resolves hits back to ``entities``.

Run:  python -m ingest.load         # (re)build data/tradecheck.duckdb from data/raw/
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import duckdb

from .normalize import NormalizedRecord, normalize_name
from .parse_canada import parse_canada
from .parse_ofac import parse_ofac

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
MANIFEST = RAW_DIR / "manifest.json"
DB_PATH = ROOT / "data" / "tradecheck.duckdb"

_SCHEMA = """
DROP TABLE IF EXISTS names;
DROP TABLE IF EXISTS entities;
CREATE TABLE entities (
    entity_id     BIGINT PRIMARY KEY,
    source_list   VARCHAR,
    source_ref    VARCHAR,
    entity_type   VARCHAR,
    primary_name  VARCHAR,
    program       VARCHAR,
    listed_date   VARCHAR,
    countries     VARCHAR,   -- JSON array
    dobs          VARCHAR,   -- JSON array
    place_of_birth VARCHAR,
    ids           VARCHAR,   -- JSON array of {type,value,country}
    source_url    VARCHAR,
    fetched_at    VARCHAR
);
CREATE TABLE names (
    entity_id   BIGINT,
    name        VARCHAR,
    name_norm   VARCHAR,
    quality     VARCHAR,     -- strong | weak | NULL
    is_primary  BOOLEAN
);
CREATE INDEX idx_names_norm ON names(name_norm);
"""


def _manifest() -> dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text())
    return {}


def _records_from_raw() -> Iterable[NormalizedRecord]:
    """Parse whichever raw files are present, using fetched_at from the manifest."""
    manifest = _manifest()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    plan = [
        ("us_sdn", "ofac_sdn.xml", lambda p, ts: parse_ofac(p, "OFAC-SDN", ts)),
        ("us_cons", "ofac_consolidated.xml", lambda p, ts: parse_ofac(p, "OFAC-CONS", ts)),
        ("ca_sema", "canada_sema.xml", lambda p, ts: parse_canada(p, ts)),
    ]
    for key, filename, parser in plan:
        path = RAW_DIR / filename
        if not path.exists():
            continue
        fetched_at = manifest.get(key, {}).get("fetched_at", now)
        yield from parser(str(path), fetched_at)


def build(records: Iterable[NormalizedRecord], db_path: str | Path = DB_PATH) -> dict:
    """(Re)build the DuckDB store from ``records``. Returns summary counts.

    Shared by the real pipeline and the test fixtures, so both exercise the
    identical load + match path.
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    try:
        for stmt in _SCHEMA.strip().split(";"):
            if stmt.strip():
                con.execute(stmt)
        ent_rows: list[tuple] = []
        name_rows: list[tuple] = []
        counts: dict[str, int] = {}

        for eid, rec in enumerate(records, start=1):
            counts[rec.source_list] = counts.get(rec.source_list, 0) + 1
            ent_rows.append((
                eid, rec.source_list, rec.source_ref, rec.entity_type,
                rec.primary_name, rec.program, rec.listed_date,
                json.dumps(rec.countries), json.dumps(rec.dobs),
                rec.place_of_birth, json.dumps(rec.ids),
                rec.source_url, rec.fetched_at,
            ))
            # primary name
            name_rows.append((eid, rec.primary_name, normalize_name(rec.primary_name), None, True))
            # aliases
            for alias in rec.aliases:
                name_rows.append((eid, alias.name, normalize_name(alias.name), alias.quality, False))

        if ent_rows:
            con.executemany(
                "INSERT INTO entities VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", ent_rows
            )
        if name_rows:
            con.executemany("INSERT INTO names VALUES (?,?,?,?,?)", name_rows)
        con.commit()

        total = len(ent_rows)
        counts["_total_entities"] = total
        counts["_total_names"] = len(name_rows)
        return counts
    finally:
        con.close()


def main() -> int:
    counts = build(_records_from_raw())
    if counts.get("_total_entities", 0) == 0:
        print(
            "No records loaded. Run `python -m ingest.fetch` first (and ensure the "
            "source hosts are reachable)."
        )
        return 1
    print("Built", DB_PATH)
    for k, v in sorted(counts.items()):
        print(f"  {k}: {v:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

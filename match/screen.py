"""Deterministic name screening over the DuckDB store.

Given a name, return a graded verdict with the evidence behind it. The verdict is
*computed* from the loaded lists (same input -> same output), never generated -- the
product's core promise. Missing data is reported as Unknown, never as Clear.

Grades (README "How we grade a hit"):
  Avoid           exact hit on a primary / strong name, or a high-confidence fuzzy hit
  Caution         fuzzy hit to review, or a weak-alias hit, or conflicting identifiers
  Unknown->Caution no list data available (never shown as clear)
  Clear*          no hits across every loaded list

Run:  python -m match.screen "KHAWA PANGA MANDRO"
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import duckdb
from rapidfuzz import fuzz, process

from ingest.load import DB_PATH
from ingest.normalize import normalize_name

# Fuzzy thresholds. 90 = "hit to review" (README); 95+ = strong match.
# Starting guesses -- tune on the test set.
CAUTION_THRESHOLD = 90
AVOID_THRESHOLD = 95

_DISCLAIMER = "Not legal advice. Screening reflects the listed sources as of the dates shown."

# Cache loaded names per (db_path, mtime) so the web app doesn't reload every request.
_CACHE: dict[tuple[str, float], list[dict]] = {}


def _mostly_lost(name: str, norm: str) -> bool:
    """True when folding to ASCII dropped most of a name (e.g. Cyrillic, Arabic).

    Such keys are fragments ("ka" from "Kaдырова") that fuzzy-match almost
    anything. Those parties stay searchable via their Latin-script names.
    """
    letters = sum(c.isalpha() for c in name)
    return letters > 0 and len(norm.replace(" ", "")) < 0.5 * letters


def _load_names(con: duckdb.DuckDBPyConnection) -> list[dict]:
    rows = con.execute(
        "SELECT entity_id, name, name_norm, quality, is_primary FROM names WHERE name_norm <> ''"
    ).fetchall()
    return [
        {"entity_id": r[0], "name": r[1], "name_norm": r[2], "quality": r[3], "is_primary": r[4]}
        for r in rows
        if not _mostly_lost(r[1], r[2])
    ]


# A query that names only part of a listed name (e.g. without the patronymic) is
# scored down so it can reach "review" but never "avoid" on its own.
PARTIAL_SCALE = 0.9


def _score(query_norm: str, name_norm: str) -> tuple[float, str]:
    """Score a candidate name. Returns (score, kind) with kind 'full' | 'partial'.

    Whole-name comparison (order-insensitive) is the default. A subset match only
    counts in one direction: the query may omit words of the listed name, but a
    short listed alias never matches inside a longer query ("Dora" must not hit
    "AgroDistribuidora").
    """
    full = fuzz.token_sort_ratio(query_norm, name_norm)
    q_tokens, n_tokens = query_norm.split(), name_norm.split()
    if len(q_tokens) >= 2 and len(n_tokens) > len(q_tokens):
        partial = fuzz.token_set_ratio(query_norm, name_norm) * PARTIAL_SCALE
        if partial > full:
            return partial, "partial"
    return full, "full"


def _names_for(db_path: Path, con: duckdb.DuckDBPyConnection) -> list[dict]:
    key = (str(db_path), db_path.stat().st_mtime if db_path.exists() else 0.0)
    cached = _CACHE.get(key)
    if cached is None:
        cached = _load_names(con)
        _CACHE[key] = cached
    return cached


def _lists_screened(con: duckdb.DuckDBPyConnection) -> list[dict]:
    rows = con.execute(
        "SELECT source_list, MAX(fetched_at) FROM entities GROUP BY source_list ORDER BY source_list"
    ).fetchall()
    return [{"source_list": r[0], "fetched_at": r[1]} for r in rows]


def status(db_path: str | Path = DB_PATH) -> dict:
    """Which lists are loaded, how many entries each holds, and when each was fetched."""
    db_path = Path(db_path)
    if not db_path.exists():
        return {"lists": []}
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        rows = con.execute(
            """SELECT source_list, COUNT(*), MAX(fetched_at), ANY_VALUE(source_url)
               FROM entities GROUP BY source_list ORDER BY source_list"""
        ).fetchall()
    finally:
        con.close()
    return {"lists": [
        {"source_list": r[0], "entries": r[1], "fetched_at": r[2], "source_url": r[3]}
        for r in rows
    ]}


def _entity(con: duckdb.DuckDBPyConnection, entity_id: int) -> dict:
    row = con.execute(
        """SELECT source_list, source_ref, entity_type, primary_name, program,
                  listed_date, countries, dobs, place_of_birth, ids, source_url, fetched_at
           FROM entities WHERE entity_id = ?""",
        [entity_id],
    ).fetchone()
    keys = ["source_list", "source_ref", "entity_type", "primary_name", "program",
            "listed_date", "countries", "dobs", "place_of_birth", "ids", "source_url", "fetched_at"]
    rec = dict(zip(keys, row))
    for jkey in ("countries", "dobs", "ids"):
        try:
            rec[jkey] = json.loads(rec[jkey]) if rec[jkey] else []
        except (TypeError, json.JSONDecodeError):
            rec[jkey] = []
    return rec


def _grade_hit(is_exact: bool, score: float, quality: str | None, is_primary: bool) -> str:
    """Return 'avoid' | 'caution' for a candidate name match."""
    weak = (quality or "").lower() == "weak"
    strong_like = is_primary or not weak  # primary, 'strong', or unflagged (Canada) names
    if is_exact and strong_like:
        return "avoid"
    if is_exact and weak:
        return "caution"
    if score >= AVOID_THRESHOLD and strong_like:
        return "avoid"
    return "caution"


def screen(
    name: str,
    db_path: str | Path = DB_PATH,
    caution_threshold: int = CAUTION_THRESHOLD,
    avoid_threshold: int = AVOID_THRESHOLD,
) -> dict:
    db_path = Path(db_path)
    query_norm = normalize_name(name)
    checked_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    base = {
        "query": name,
        "query_normalized": query_norm,
        "checked_at": checked_at,
        "disclaimer": _DISCLAIMER,
        "hits": [],
    }

    if not db_path.exists():
        return {**base, "verdict": "Unknown", "lists_screened": [],
                "message": "No sanctions data loaded yet -- treat as Unknown, not Clear."}

    con = duckdb.connect(str(db_path), read_only=True)
    try:
        lists_screened = _lists_screened(con)
        if not lists_screened or not query_norm:
            return {**base, "verdict": "Unknown", "lists_screened": lists_screened,
                    "message": "No list data available for this query -- Unknown, not Clear."}

        names = _names_for(db_path, con)
        norms = [n["name_norm"] for n in names]

        # token_set_ratio is an upper bound on _score, so it is a safe C-speed prefilter.
        candidates = process.extract(
            query_norm, norms, scorer=fuzz.token_set_ratio,
            score_cutoff=caution_threshold, limit=1000,
        )

        # Best grade + score per entity.
        best: dict[int, dict] = {}
        for _matched_norm, _upper, idx in candidates:
            meta = names[idx]
            score, kind = _score(query_norm, meta["name_norm"])
            if score < caution_threshold:
                continue
            is_exact = meta["name_norm"] == query_norm
            level = "caution" if kind == "partial" else _grade_hit(
                is_exact, score, meta["quality"], meta["is_primary"])
            eid = meta["entity_id"]
            prior = best.get(eid)
            if prior is None or score > prior["score"] or (level == "avoid" and prior["level"] != "avoid"):
                best[eid] = {
                    "score": round(float(score), 1),
                    "level": level,
                    "matched_name": meta["name"],
                    "match_type": "exact" if is_exact else ("partial" if kind == "partial" else "fuzzy"),
                    "quality": "primary" if meta["is_primary"] else meta["quality"],
                }

        hits = []
        for eid, h in best.items():
            hits.append({**h, "entity": _entity(con, eid)})
        hits.sort(key=lambda x: (x["level"] != "avoid", -x["score"]))

        if not hits:
            verdict = "Clear"
        elif any(h["level"] == "avoid" for h in hits):
            verdict = "Avoid"
        else:
            verdict = "Caution"

        result = {**base, "verdict": verdict, "lists_screened": lists_screened, "hits": hits}
        if verdict == "Clear":
            srcs = ", ".join(l["source_list"] for l in lists_screened)
            result["message"] = f"No hits across {srcs}. {_DISCLAIMER}"
        return result
    finally:
        con.close()


def main() -> int:
    if len(sys.argv) < 2:
        print('usage: python -m match.screen "name to screen"', file=sys.stderr)
        return 2
    result = screen(" ".join(sys.argv[1:]))
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""End-to-end: parse fixtures -> load DuckDB -> screen -> graded verdict.

Covers the full verdict taxonomy (README discipline: >=1 known hit per list).
"""

from match.screen import screen


def test_avoid_exact_ofac_primary(db):
    res = screen("KHAWA PANGA MANDRO", db)
    assert res["verdict"] == "Avoid"
    assert res["hits"]
    assert res["hits"][0]["entity"]["source_list"] == "OFAC-SDN"
    assert "DRCONGO" in (res["hits"][0]["entity"]["program"] or "")


def test_caution_weak_alias(db):
    # "Chief Kahwa" is a weak OFAC a.k.a. -> flagged for review, not an auto-match.
    res = screen("Chief Kahwa", db)
    assert res["verdict"] == "Caution"
    assert any(h["quality"] == "weak" for h in res["hits"])


def test_clear_for_unlisted_name(db):
    res = screen("AgroDistribuidora del Bajío SA de CV", db)
    assert res["verdict"] == "Clear"
    assert res["hits"] == []
    assert "message" in res


def test_canada_sema_hit(db):
    res = screen("Ivan Testov", db)
    assert res["verdict"] == "Avoid"
    assert res["hits"][0]["entity"]["source_list"] == "CA-SEMA"


def test_both_lists_screened_with_timestamps(db):
    res = screen("anyone at all", db)
    screened = {l["source_list"]: l["fetched_at"] for l in res["lists_screened"]}
    assert {"OFAC-SDN", "CA-SEMA"} <= set(screened)
    assert all(ts for ts in screened.values())
    assert res["checked_at"]


def test_unknown_not_clear_when_no_data(tmp_path):
    res = screen("whoever", tmp_path / "missing.duckdb")
    assert res["verdict"] == "Unknown"
    assert res["hits"] == []


def test_short_alias_does_not_match_inside_longer_name():
    from match.screen import _score
    # Live OFAC carries a weak alias "Dora"; it must not flag "AgroDistribuidora".
    score, _ = _score("agrodistribuidora del bajio", "dora")
    assert score < 90


def test_query_may_omit_middle_names_but_only_reaches_review():
    from match.screen import _score
    score, kind = _score("khazalbek atabekov", "khazalbek bakhtibekovich atabekov")
    assert kind == "partial" and 90 <= score < 95


def test_non_latin_names_that_fold_to_fragments_are_skipped():
    from match.screen import _mostly_lost
    from ingest.normalize import normalize_name
    name = "Аймани Несиевна Kaдырова"
    assert _mostly_lost(name, normalize_name(name))
    assert not _mostly_lost("Khawa Panga MANDRO", "khawa panga mandro")


def test_status_reports_lists_and_counts(db):
    from match.screen import status
    res = status(db)
    by_list = {l["source_list"]: l for l in res["lists"]}
    assert by_list["OFAC-SDN"]["entries"] == 2
    assert by_list["CA-SEMA"]["fetched_at"]


def test_status_without_data(tmp_path):
    from match.screen import status
    assert status(tmp_path / "missing.duckdb")["lists"] == []

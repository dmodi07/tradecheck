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

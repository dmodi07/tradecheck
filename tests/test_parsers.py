from pathlib import Path

from ingest.parse_canada import parse_canada
from ingest.parse_ofac import parse_ofac

FIXTURES = Path(__file__).parent / "fixtures"
TS = "2026-09-22T00:00:00+00:00"


def test_ofac_parses_khawa_and_entity():
    recs = list(parse_ofac(str(FIXTURES / "ofac_sdn_sample.xml"), "OFAC-SDN", TS))
    assert len(recs) == 2

    khawa = next(r for r in recs if r.source_ref == "10033")
    assert khawa.entity_type == "individual"
    assert "MANDRO" in khawa.primary_name
    assert khawa.program and "DRCONGO" in khawa.program
    # strong/weak alias flags carried through from <aka category=...>
    assert any(a.quality == "weak" and "KAHWA" in a.name.upper() for a in khawa.aliases)
    assert any(a.quality == "strong" for a in khawa.aliases)
    assert khawa.dobs and "1973" in khawa.dobs[0]
    assert "Congo" in (khawa.place_of_birth or "")
    assert khawa.fetched_at == TS

    entity = next(r for r in recs if r.source_ref == "99001")
    assert entity.entity_type == "entity"
    assert entity.ids and entity.ids[0]["value"] == "TEST-000-001"


def test_canada_parses_individual_and_entity():
    recs = list(parse_canada(str(FIXTURES / "canada_sema_sample.xml"), TS))
    assert len(recs) == 2

    ivan = next(r for r in recs if r.entity_type == "individual")
    assert ivan.primary_name == "Ivan TESTOV"
    assert ivan.source_list == "CA-SEMA"
    assert ivan.listed_date == "2022/03/22"
    assert any("Testov" in a.name for a in ivan.aliases)
    assert ivan.program and "Testlandia" in ivan.program

    entity = next(r for r in recs if r.entity_type == "entity")
    assert "Synthetic Test Trading" in entity.primary_name

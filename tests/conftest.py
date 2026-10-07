"""Shared test fixtures: build a DuckDB store from the sample XML fixtures."""

from __future__ import annotations

import itertools
from pathlib import Path

import pytest

from ingest.load import build
from ingest.parse_canada import parse_canada
from ingest.parse_ofac import parse_ofac

FIXTURES = Path(__file__).parent / "fixtures"
TS = "2026-09-22T00:00:00+00:00"


@pytest.fixture
def db(tmp_path):
    """A freshly built DuckDB store loaded from the OFAC + Canada fixtures."""
    db_path = tmp_path / "test.duckdb"
    records = itertools.chain(
        parse_ofac(str(FIXTURES / "ofac_sdn_sample.xml"), "OFAC-SDN", TS),
        parse_canada(str(FIXTURES / "canada_sema_sample.xml"), TS),
    )
    build(records, db_path)
    return db_path

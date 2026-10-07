# Running TradeCheck (Build Session 2)

US + Canada sanctions screening: direct-from-source ingestion → DuckDB → transparent matching.

## Setup

```bash
pip install -r requirements.txt
```

## 1. Fetch the lists (direct from source)

```bash
python -m ingest.fetch           # OFAC SDN + Consolidated, Canada SEMA/JVCFOA
python -m ingest.fetch --only ca_sema us_sdn   # just the must-haves
```

Raw files land in `data/raw/` with a `manifest.json` recording the URL, byte count,
SHA-256 and `fetched_at` for each — the provenance behind every answer.

> **Network note.** The sources are free government data with no key. In a **cloud
> session** the egress proxy may block them (`403` on connect). Add
> `sanctionslistservice.ofac.treas.gov` and `www.international.gc.ca` under the
> environment's **Network access → Allowed domains**, or run the fetch on a local
> machine. Local laptop runs need no allowlisting.

## 2. Build the database

```bash
python -m ingest.load            # (re)builds data/tradecheck.duckdb from data/raw/
```

Two tables: `entities` (one row per party, full evidence) and `names` (one row per
name variant, carrying the normalized match key + OFAC strong/weak flag).

## 3. Screen a name (CLI)

```bash
python -m match.screen "KHAWA PANGA MANDRO"
python -m match.screen "AgroDistribuidora del Bajío SA de CV"
```

## 4. Run the web app

```bash
uvicorn app.main:app --reload
# open http://127.0.0.1:8000
```

## Tests (run offline, no network)

```bash
pytest
```

Parses the bundled fixtures (including the real public OFAC *Khawa Panga Mandro*
record), builds a DuckDB store, and asserts the full verdict taxonomy:
Avoid (exact SDN hit) · Caution (weak alias) · Clear\* (unlisted) · Canada SEMA hit ·
Unknown (no data).

## Data sources

| List | Endpoint |
| --- | --- |
| US — OFAC SDN | `https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/SDN.XML` |
| US — OFAC Consolidated (non-SDN) | `.../exports/CONSOLIDATED.XML` |
| Canada — SEMA/JVCFOA | `https://www.international.gc.ca/world-monde/assets/office_docs/international_relations-relations_internationales/sanctions/sema-lmes.xml` |

**Coverage caveat:** Canada's *autonomous* list covers SEMA + JVCFOA only. Canada's
UN-mandated measures (e.g. the DRC regime) are enacted separately under the UN Act and
are not in this file — a disclosed gap, shown honestly rather than rendered as "clear".

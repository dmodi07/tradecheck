# TradeCheck

**A free sanctions check for Canadian small businesses, with the source and date behind every answer. A chatbot's "looks fine" isn't due diligence.**

## The problem

### It's real, and it starts at home

I'm in Canada, and this is built for Canadian small businesses first.

The spark: a textile business owner in India spent **over four months** trying to find and assess trading partners in Canada — calling friends here (including me), searching online for names, browsing Instagram for sellers. I was part of that search, and I watched how much guesswork went into decisions that deserved facts.

The same wall stands on this side of the Pacific: a BC farmer wondering whether they can sell crops in Mexico, the Caribbean, or the US; a Canadian jewellery maker exporting for the first time; an importer in Surrey who needs to vet a new overseas supplier. And there's a Canadian legal reason this matters: Canadians doing business abroad must comply with Canadian sanctions law (SEMA) — "I didn't know" is not a compliance strategy.

**Root cause:** the information exists, but it is spread across government portals and sanctions lists in different countries, formats, and languages. One question every one of these businesses must answer first: *"Is this name on a sanctions list?"* Today that means checking the US, EU, UK, UN and Canadian lists separately, or paying for an enterprise tool built for someone else.

### Who this is for (and who it's not for)

Multinationals already have their own compliance stacks and legal teams. **This is for the Canadian small, private, family-owned business** — the BC farmer eyeing Mexico, the Vancouver artisan exporting for the first time, the Surrey importer vetting a new supplier. They have a laptop and a deadline, not a compliance department. They get self-serve answers: no sales call, no enterprise contract.

### Measured baseline (first pass run Oct 6, 2026)

Test buyer: **"AgroDistribuidora del Bajío SA de CV"** (fictional Mexican distributor). Question: *is it sanctioned under Canadian, US, EU, UK, or UN lists?*

| Question | Minutes | # sources | Confidence (1–5) |
| --- | --- | --- | --- |
| Is my buyer/distributor sanctioned — under Canadian, US, EU, UK, or UN lists? | \~20 | 10+ across 5 portals | 2 |

What the run surfaced:

- **Five jurisdictions, five different doors.** OFAC has its own web search (with a confidence slider); the UN publishes a raw 5,285-line XML with no name search; the EU list lives on a data-portal page; the UK has a gov.uk publications page plus a separate FCDO search tool; Canada's consolidated SEMA/JVCFOA list sits with Global Affairs Canada. Different formats, different update cadences (OFAC: no fixed schedule; OFSI: every business day; EU: multiple times/week; UN: irregular).
- **Proving a negative by hand is the hard part.** Finding a *hit* is easy; being *confident there is no hit* across five portals — each searched separately, in different formats — is what eats the time. OFAC itself warns that a clean result in its own tool "does not immunize you from liability."
- **Free single-list tools exist; a free unified one doesn't.** OFAC's own search, third-party OFAC checkers, per-list mirrors (some rate-limited, e.g. 10 searches/hour) — each covers one jurisdiction. None gives one free search across all five with explained matches.

**Chatbot test:** asked a general-purpose chatbot the same question. Result: **unverifiable** — no live list access, no dated sources; the only honest answer is abstention, and abstention isn't due diligence. (Even for a *known* sanctioned name from our UN sample, the chatbot answers from stale training data and cannot confirm current listing status or cite list + date.)

*First pass run by AI assistant using the same public portals a human would; the team should re-run by hand and replace these numbers before Demo Day.*

## Why not just ask AI?

Fair question. We asked it ourselves, and here's what we found:

1. **AI answers from memory; we answer from live records, with receipts.** Sanctions lists change daily and a model's training data is months old. When a chatbot doesn't know, it guesses confidently. A wrong "you're clear" before a trade deal is dangerous.
2. **You can't show a chat transcript to a bank.** This produces a record: these lists, this date, this match, this evidence. That's the actual product for a small business doing due diligence.
3. **Chatbots can't say "I don't know."** Ours can, and does. Missing data shows as *Unknown*, never green. We think that honesty is the whole differentiation.
4. **Same input, same answer.** Ask a chatbot twice, get two answers. Ours runs the same matching logic every time, so results are testable and comparable.

## Why this lasts beyond the datathon

Honestly, the valuable part isn't the code, it's the data pipeline. A daily-refreshed sanctions dataset with transparent matching stays useful as long as governments keep publishing lists, which is forever. Enterprise vendors serve compliance teams; nobody serves the small exporter, and that gap doesn't close on its own. Every honest "unknown" and every dated source earns the next user's trust. And it grows: sanctions screening is module one, tariffs and firm checks come next. Same pipeline, same users.

## Data evidence

| Source | What it gives | Access | Licence / terms | Status |
| --- | --- | --- | --- | --- |
| OpenSanctions | Consolidated dataset from dozens of official lists — US, EU, UK, UN, **Canada (SEMA)**, plus PEPs and debarment; bulk CSV/JSON, updated daily | Free bulk download, no key | **CC-BY-NC 4.0 — free for non-commercial use** (fits the datathon; commercial use needs a paid licence) | To ingest in Build Session 2 |
| UN Security Council Consolidated List | Direct source pull | Free XML | Public government data | ✅ Verified live pull Oct 3, 2026 — 5,285-line XML |
| Reference pattern | `gsmiguel/sanctions_lists_etl`: 4-list (OFAC/EU/UN/UK) ETL running daily via GitHub Actions | Open source | — | Proves the pipeline pattern is feasible |

**Key simplification:** instead of four separate ingestion pipelines, OpenSanctions already consolidates the major lists into one daily dataset. Our verified UN direct pull stays as a provenance cross-check.

### Signal check (done Oct 3, on a 10-record UN sample)

- Searching **"kawa"** → 1 person (KHAWA PANGA MANDRO) with **8 aliases**; confidence from the UN's own alias-quality labels: primary-name match 100, "Good" alias 85, "Low" alias 60.
- Searching **"dipen"** → clean no-hit verdict, no false positives in the sample.

**Test discipline:** the test set must include at least one known sanctioned entity per screened list. *A screen that never returns a hit is untested.*

## How we grade a hit

**Name matching:**

1. Normalize: lowercase, strip legal suffixes (Ltd, PLC, SAS, SARL, KK, …), fold accents.
2. Join on exact registry/ID first; fuzzy-match names only as fallback.
3. Fuzzy threshold ≈ 90 = **hit to review, never an automatic match**. Tune on test cases.

**The grades:**

| Level | Rule |
| --- | --- |
| **Avoid** | Strong sanctions hit on the subject |
| **Caution** | Fuzzy hit needing review, or conflicting identifiers |
| **Unknown → Caution** | No data for this name/list. Never shown as clear |
| **Clear\*** | No hits across all lists checked |

\* "Clear" always shows: *"Based on sources X as of date Y. Not legal advice."* Missing data must never render as green.

## Scope

**This microproduct (Build Sessions 2–3 + Demo Day):** one search box over consolidated sanctions data with transparent, explainable matches — built for the small business use case above.

**Out of scope for the datathon:** legal advice, automated block/allow decisions, transaction monitoring.

**After Demo Day:** extend the same pattern to tariffs/duties by product code and firm-registry checks. One place for "can I trade X with country Y?" The world-map explorer idea, but grounded in official data.

## Demo script (4 cases, each live in under 5 seconds)

All four run on live US + Canada data and are one click away in the UI ("Try an example").

1. **No match** — "AgroDistribuidora del Bajío SA de CV" (fictional Mexican buyer): no hits → *No match* stamp, with the lists checked and their download dates.
2. **Review** — "Mohammad Ali": a common name with ~27 similar listings → *Review*, with each listing's birth date, country and IDs laid out for comparison. Shows why the tool never auto-blocks on a name alone.
3. **Listed** — "Rosneft": exact hit on OFAC (SDN + non-SDN) and Canada SEMA → *Listed*, with registration and tax IDs and official source links.
4. **Listed on both lists** — "Vladimir Putin": one party, listed by both the US and Canada, shown as a single entry with both sources.

> The earlier "Chief Kahwa → Caution" case relied on a *Low-quality* UN alias. In the live OFAC
> data that alias is *strong*, so it returns Listed; the UN list is out of the US + Canada scope.

## Key links

**Data sources**

- OpenSanctions — bulk downloads and docs: https://www.opensanctions.org/ · https://www.opensanctions.org/docs/
- UN Consolidated List (raw XML): https://scsanctions.un.org/resources/xml/en/consolidated.xml
- OFAC Sanctions List Search: https://sanctionssearch.ofac.treas.gov/
- EU consolidated list (data portal): https://data.europa.eu/data/datasets/consolidated-list-of-persons-groups-and-entities-subject-to-eu-financial-sanctions?locale=en
- UK: GOV.UK — search "OFSI consolidated list of targets" (CSV/XLS download)
- Canada: Global Affairs Canada — Consolidated Canadian Autonomous Sanctions List (SEMA/JVCFOA)

**References**

- Trilemma Request for Microproducts: https://build.trilemma.foundation/docs/request-for-microproducts
- Build Session 1 checklist: https://github.com/TrilemmaFoundation/Datathon-Season-2026/blob/main/build%20session%20checklist/build-session-1.md
- Pipeline pattern reference (4-list ETL, daily): https://github.com/gsmiguel/sanctions\_lists\_etl/blob/HEAD/README.md

## Build Session 2 plan

**Demo scope (decided Oct 7):** narrowed to **US + Canada** — the legal must (Canada/SEMA)
plus the dominant trade corridor (US/OFAC). Pulling **direct from the two government sources**
(not OpenSanctions) removes the CC-BY-NC commercial-licence risk and strengthens provenance.
See [`RUN.md`](RUN.md) for commands.

```
OFAC SDN + Consolidated (XML) ─┐
Canada SEMA/JVCFOA (XML) ───────┼─► normalize ─► DuckDB ─► rapidfuzz match ─► verdict + evidence ─► single-page UI
```

- [x] Ingest the two lists directly from source (DuckDB); provenance (`fetched_at`, SHA-256) in `manifest.json`
- [x] Normalization schema: name, aliases + quality, DOB, nationality, IDs, source list, program, listed date, `fetched_at` on every field
- [x] Matching pipeline (rapidfuzz) with transparent per-hit confidence scores
- [x] Single search UI: per-hit evidence, source links, verdict, "checked at" timestamp
- [ ] 3 scripted demo cases (clear / caution / avoid) on **live** data — logic validated offline via fixtures; pending first live fetch
- [x] "Not legal advice" disclaimer on every result

**Stack (all free):** Python, DuckDB, FastAPI, rapidfuzz, one static HTML page.

**Open questions (to settle in Build Session 2):**

- DuckDB vs SQLite for the local store. Leaning DuckDB, will decide while spiking.
- The 90 fuzzy-match threshold is a starting guess, not a tested number. Tune on the test set.
- Who owns what: TODO (team to fill in).

### Open risks

- **Licence:** OpenSanctions bulk is non-commercial — fine for the datathon, must switch to a paid licence before any commercial use.
- **Attribution:** CC-BY-NC requires crediting OpenSanctions — attribution goes in the UI footer and the repo.
- **False confidence:** transliteration and common names cause false positives — measured on the test set, not hand-waved.
- **Staleness:** lists update on different cadences; every field shows `fetched_at`.

## Team

- Dipen Modi, Mansi Purohit, Dhruv Patel
- Who owns what: Dipen - data, UI; Mansi - TBD; Dhruv - TBD.

## Repo status

Build Session 1 (Oct 5): framing + this README. Build Session 2 (Oct 7): working ingestion and search —
US + Canada direct-pull pipeline (OFAC SDN/Consolidated + Canada SEMA/JVCFOA) → DuckDB → rapidfuzz
screening → FastAPI single-page UI. End-to-end tested offline (`pytest`, 24 passing). See [`RUN.md`](RUN.md).
"""Parse the Consolidated Canadian Autonomous Sanctions List (sema-lmes.xml).

Covers SEMA + JVCFOA (autonomous) listings only. NOTE: Canada's UN-mandated
sanctions (e.g. the DRC regime) are enacted separately under the United Nations
Act and are NOT in this file -- a deliberate, disclosed coverage gap.

The live file uses bilingual tags such as ``<LastName-NomDeFamille>``. Records are
matched on the English half of each tag (before the first ``-``), case-insensitively,
against several candidate names per field, so minor schema drift doesn't silently
drop every record. Verified against the live file on 2026-10-07 (5,707 records).
"""

from __future__ import annotations

from typing import Iterator

from lxml import etree

from .normalize import Alias, NormalizedRecord

SOURCE_URL = (
    "https://www.international.gc.ca/world-monde/assets/office_docs/"
    "international_relations-relations_internationales/sanctions/sema-lmes.xml"
)

# Candidate tag names (lowercased) per logical field.
_FIELDS = {
    "last_name": ("lastname", "last_name", "surname", "nom"),
    "given_name": ("givenname", "given_name", "firstname", "first_name", "prenom"),
    "entity": ("entityorship", "entity", "entityname", "entity_name", "name", "corporatename"),
    "aliases": ("aliases", "alias", "aka", "alsoknownas"),
    "dob": ("dateofbirth", "dob", "dateofbirthorshipbuilddate", "birthdate"),
    "country": ("country", "pays"),
    "schedule": ("schedule", "annex", "annexe"),
    "program": ("program", "regulation", "regulations", "reglement"),
    "item": ("item", "itemnumber", "item_number", "ref", "referencenumber"),
    "listed_date": ("dateoflisting", "listingdate", "date_of_listing", "datelisted"),
    "title": ("titleorshiptype", "title", "titre"),
    "imo": ("shipimonumber", "imo", "imonumber"),
}
# Flatten for reverse lookup: tag -> logical field.
_TAG_TO_FIELD = {tag: field for field, tags in _FIELDS.items() for tag in tags}

_ALIAS_SEP = (";", ",", "|")


def _ln(el: etree._Element) -> str:
    return etree.QName(el).localname


def _field_key(el: etree._Element) -> str:
    """``LastName-NomDeFamille`` -> ``lastname`` (English half of a bilingual tag)."""
    return _ln(el).split("-", 1)[0].lower()


def _english(text: str | None) -> str | None:
    """``Russia / Russie`` -> ``Russia``. Leaves single-language values alone."""
    return text.split(" / ", 1)[0].strip() if text else text


def _record_fields(record: etree._Element) -> dict[str, str]:
    """Collapse a <record>'s children into {logical_field: text}."""
    out: dict[str, str] = {}
    for child in record:
        field = _TAG_TO_FIELD.get(_field_key(child))
        if field and child.text and child.text.strip() and field not in out:
            out[field] = child.text.strip()
    return out


def _split_aliases(raw: str | None) -> list[Alias]:
    if not raw:
        return []
    parts = [raw]
    for sep in _ALIAS_SEP:
        parts = [p for chunk in parts for p in chunk.split(sep)]
    return [Alias(name=p.strip(), quality=None) for p in parts if p.strip()]


def _parse_record(record: etree._Element, fetched_at: str) -> NormalizedRecord | None:
    f = _record_fields(record)

    entity_name = f.get("entity")
    given = f.get("given_name")
    last = f.get("last_name")
    person_name = " ".join(p for p in (given, last) if p).strip()

    aliases = _split_aliases(f.get("aliases"))
    ids: list[dict[str, str]] = []
    imo = f.get("imo", "")
    if imo.replace(" ", "").isdigit():
        ids.append({"type": "IMO", "value": imo.replace(" ", ""), "country": ""})
    elif imo:
        # The live file occasionally carries a native-script name in the IMO column.
        aliases.extend(_split_aliases(imo))

    if entity_name and not person_name:
        entity_type = "vessel" if ids else "entity"
        primary_name = entity_name
    elif person_name:
        entity_type = "individual"
        primary_name = person_name
    else:
        return None  # nothing nameable in this record

    regime = _english(f.get("country"))
    schedule = f.get("schedule")
    program_bits = [
        f.get("program") or regime,
        f"Schedule {schedule}" if schedule else None,
    ]
    program_bits = [b for b in program_bits if b]

    # Item numbers restart per regime, so qualify them to keep refs unique.
    item = f.get("item", "")
    source_ref = f"{regime} #{item}" if regime and item else item

    return NormalizedRecord(
        source_list="CA-SEMA",
        source_ref=source_ref,
        entity_type=entity_type,
        primary_name=primary_name,
        source_url=SOURCE_URL,
        fetched_at=fetched_at,
        aliases=aliases,
        dobs=[f["dob"]] if f.get("dob") else [],
        countries=[regime] if regime else [],
        place_of_birth=None,
        ids=ids,
        program=" / ".join(program_bits) if program_bits else None,
        listed_date=f.get("listed_date"),
    )


def parse_canada(path: str, fetched_at: str) -> Iterator[NormalizedRecord]:
    """Stream NormalizedRecords from Canada's sema-lmes.xml at ``path``."""
    for _event, record in etree.iterparse(path, events=("end",)):
        if _ln(record).lower() != "record":
            continue
        rec = _parse_record(record, fetched_at)
        if rec is not None:
            yield rec
        record.clear()
        while record.getprevious() is not None:
            del record.getparent()[0]

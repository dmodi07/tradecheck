"""Parse OFAC's *classic* SDN / Consolidated XML into NormalizedRecord objects.

The classic format (namespace ``http://tempuri.org/sdnList.xsd``) is one
``<sdnEntry>`` per party and, crucially, carries the strong/weak alias flag we
need for the "Caution" grade directly on each ``<aka>`` element::

    <sdnEntry>
      <uid>10033</uid>
      <firstName>Khawa Panga</firstName>
      <lastName>MANDRO</lastName>
      <sdnType>Individual</sdnType>
      <programList><program>DRCONGO</program></programList>
      <akaList>
        <aka><type>a.k.a.</type><category>weak</category>
             <firstName>Chief</firstName><lastName>KAHWA</lastName></aka>
      </akaList>
      ...
    </sdnEntry>

Both ``SDN.XML`` and the consolidated ``CONSOLIDATED.XML`` use this schema, so
one parser handles both; pass the ``source_list`` label.
"""

from __future__ import annotations

from typing import Iterator

from lxml import etree

from .normalize import Alias, NormalizedRecord

# Public landing pages used for per-hit provenance links.
SOURCE_URLS = {
    "OFAC-SDN": "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/SDN.XML",
    "OFAC-CONS": "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/CONSOLIDATED.XML",
}


def _ln(el: etree._Element) -> str:
    """Local tag name, ignoring namespace."""
    return etree.QName(el).localname


def _child(el: etree._Element, name: str) -> etree._Element | None:
    for c in el:
        if _ln(c) == name:
            return c
    return None


def _text(el: etree._Element | None, name: str) -> str | None:
    if el is None:
        return None
    c = _child(el, name)
    if c is not None and c.text and c.text.strip():
        return c.text.strip()
    return None


def _join_name(first: str | None, last: str | None) -> str:
    return " ".join(p for p in (first, last) if p).strip()


def _parse_entry(entry: etree._Element, source_list: str, fetched_at: str) -> NormalizedRecord:
    uid = _text(entry, "uid") or ""
    first = _text(entry, "firstName")
    last = _text(entry, "lastName")
    sdn_type = (_text(entry, "sdnType") or "").lower()
    entity_type = "individual" if sdn_type == "individual" else (
        "vessel" if sdn_type == "vessel" else "entity"
    )

    # Programs
    programs: list[str] = []
    prog_list = _child(entry, "programList")
    if prog_list is not None:
        programs = [c.text.strip() for c in prog_list if _ln(c) == "program" and c.text]

    # Aliases (with strong/weak quality)
    aliases: list[Alias] = []
    aka_list = _child(entry, "akaList")
    if aka_list is not None:
        for aka in aka_list:
            if _ln(aka) != "aka":
                continue
            name = _join_name(_text(aka, "firstName"), _text(aka, "lastName"))
            if not name:
                continue
            quality = (_text(aka, "category") or "").lower() or None
            aliases.append(Alias(name=name, quality=quality))

    # Dates of birth
    dobs: list[str] = []
    dob_list = _child(entry, "dateOfBirthList")
    if dob_list is not None:
        for item in dob_list:
            dob = _text(item, "dateOfBirth")
            if dob:
                dobs.append(dob)

    # Place of birth (first one)
    place_of_birth = None
    pob_list = _child(entry, "placeOfBirthList")
    if pob_list is not None:
        for item in pob_list:
            place_of_birth = _text(item, "placeOfBirth")
            if place_of_birth:
                break

    # Countries: nationality + citizenship
    countries: list[str] = []
    for list_tag, item_tag in (("nationalityList", "nationality"), ("citizenshipList", "citizenship")):
        container = _child(entry, list_tag)
        if container is not None:
            for item in container:
                c = _text(item, "country")
                if c and c not in countries:
                    countries.append(c)

    # Identity documents
    ids: list[dict[str, str]] = []
    id_list = _child(entry, "idList")
    if id_list is not None:
        for item in id_list:
            if _ln(item) != "id":
                continue
            id_type = _text(item, "idType")
            id_number = _text(item, "idNumber")
            if id_number:
                ids.append({
                    "type": id_type or "ID",
                    "value": id_number,
                    "country": _text(item, "idCountry") or "",
                })

    return NormalizedRecord(
        source_list=source_list,
        source_ref=uid,
        entity_type=entity_type,
        primary_name=_join_name(first, last),
        source_url=SOURCE_URLS.get(source_list, ""),
        fetched_at=fetched_at,
        aliases=aliases,
        dobs=dobs,
        countries=countries,
        place_of_birth=place_of_birth,
        ids=ids,
        program=", ".join(programs) if programs else None,
        listed_date=None,  # classic SDN XML has no per-entry listing date
    )


def parse_ofac(path: str, source_list: str, fetched_at: str) -> Iterator[NormalizedRecord]:
    """Stream NormalizedRecords from an OFAC classic XML file at ``path``.

    Uses iterparse + element clearing so the ~29 MB SDN file stays memory-light.
    """
    # Match <sdnEntry> in any namespace.
    for _event, entry in etree.iterparse(path, events=("end",)):
        if _ln(entry) != "sdnEntry":
            continue
        yield _parse_entry(entry, source_list, fetched_at)
        entry.clear()
        # Drop preceding siblings to keep memory flat.
        while entry.getprevious() is not None:
            del entry.getparent()[0]

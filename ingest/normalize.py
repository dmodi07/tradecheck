"""Shared normalized record schema and name-normalization helpers.

Both the OFAC and Global Affairs Canada parsers emit ``NormalizedRecord`` objects,
so the loader and matcher never need to know which list a record came from.

Name normalization follows the README's "How we grade a hit" rules:
lowercase, strip legal suffixes (Ltd, PLC, SA de CV, ...), fold accents.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field, asdict
from typing import Any

# Legal-entity suffixes to strip from the END of a normalized name.
# Multi-word phrases are matched before single tokens (see _SUFFIX_PHRASES ordering).
_SUFFIXES: list[str] = [
    # multi-word first
    "sa de cv", "s a de c v", "s de rl de cv", "s de rl", "c v",
    "sp z oo", "pte ltd", "pty ltd", "co ltd", "and co", "e hf",
    # single token
    "ltd", "limited", "plc", "inc", "incorporated", "llc", "llp", "lp",
    "corp", "corporation", "co", "company", "cia", "compania",
    "sa", "sas", "sarl", "srl", "spa", "sl", "slu", "sro", "spzoo",
    "ag", "gmbh", "mbh", "kg", "ohg", "eg",
    "bv", "nv", "oy", "ab", "as", "aps",
    "kk", "gk", "yk",
    "pjsc", "ojsc", "cjsc", "jsc", "oao", "ooo", "zao", "pao",
    "pty", " pt", "tbk", "bhd", "sdn", "sdn bhd",
    "fze", "fzco", "fze llc", "wll", "psc",
]
# Longer phrases (more tokens) must be tried first so "sa de cv" wins over "cv".
_SUFFIX_PHRASES: list[list[str]] = sorted(
    (s.split() for s in _SUFFIXES), key=len, reverse=True
)

_PUNCT_RE = re.compile(r"[^a-z0-9 ]+")
_WS_RE = re.compile(r"\s+")


def fold_accents(text: str) -> str:
    """Strip diacritics via NFKD decomposition (é -> e, ü -> u)."""
    decomposed = unicodedata.normalize("NFKD", text)
    return decomposed.encode("ascii", "ignore").decode("ascii")


def normalize_name(raw: str | None) -> str:
    """Return a comparable form of ``raw``: lowercased, de-accented, de-punctuated,
    with trailing legal suffixes removed. Used as the join/fuzzy-match key."""
    if not raw:
        return ""
    s = fold_accents(raw).lower()
    s = _PUNCT_RE.sub(" ", s)
    s = _WS_RE.sub(" ", s).strip()
    tokens = s.split()
    changed = True
    while changed and tokens:
        changed = False
        for phrase in _SUFFIX_PHRASES:
            n = len(phrase)
            if n < len(tokens) and tokens[-n:] == phrase:
                # keep at least one token so a name never normalizes to empty
                tokens = tokens[:-n]
                changed = True
                break
    return " ".join(tokens)


@dataclass
class Alias:
    name: str
    # "strong" | "weak" for OFAC; None for Canada (no quality flag published).
    quality: str | None = None


@dataclass
class NormalizedRecord:
    """One sanctioned party, normalized across source lists."""

    source_list: str          # OFAC-SDN | OFAC-CONS | CA-SEMA
    source_ref: str           # OFAC uid / Canada item number
    entity_type: str          # individual | entity | vessel
    primary_name: str
    source_url: str
    fetched_at: str           # ISO-8601 UTC; provenance stamp on every record
    aliases: list[Alias] = field(default_factory=list)
    dobs: list[str] = field(default_factory=list)
    countries: list[str] = field(default_factory=list)
    place_of_birth: str | None = None
    ids: list[dict[str, str]] = field(default_factory=list)   # {type, value, country}
    program: str | None = None       # OFAC program / Canada regulation + schedule
    listed_date: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

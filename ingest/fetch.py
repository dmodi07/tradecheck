"""Download the US (OFAC) and Canada (GAC) sanctions lists directly from source.

Writes raw files to ``data/raw/`` and a ``manifest.json`` recording the URL,
``fetched_at`` (ISO-8601 UTC), byte size and SHA-256 for every file -- the
provenance the product promises ("source and date behind every answer").

Both sources are free government data with no key and no licence restriction.

Run:  python -m ingest.fetch            # all lists
      python -m ingest.fetch --only ca  # just Canada
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
MANIFEST = RAW_DIR / "manifest.json"

# key -> (url, local filename). SDN + Canada are must-haves; CONS is optional.
SOURCES: dict[str, tuple[str, str]] = {
    "us_sdn": (
        "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/SDN.XML",
        "ofac_sdn.xml",
    ),
    "us_cons": (
        "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/CONSOLIDATED.XML",
        "ofac_consolidated.xml",
    ),
    "ca_sema": (
        "https://www.international.gc.ca/world-monde/assets/office_docs/"
        "international_relations-relations_internationales/sanctions/sema-lmes.xml",
        "canada_sema.xml",
    ),
}

# Some government endpoints reject empty/default user agents.
HEADERS = {"User-Agent": "TradeCheck/0.1 (sanctions screening; +https://github.com/dmodi07/tradecheck)"}


def _download(url: str, dest: Path, retries: int = 4) -> dict:
    delay = 2
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with requests.get(url, headers=HEADERS, stream=True, timeout=60) as resp:
                resp.raise_for_status()
                sha = hashlib.sha256()
                size = 0
                with open(dest, "wb") as fh:
                    for chunk in resp.iter_content(chunk_size=65536):
                        if chunk:
                            fh.write(chunk)
                            sha.update(chunk)
                            size += len(chunk)
            return {
                "url": url,
                "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "bytes": size,
                "sha256": sha.hexdigest(),
            }
        except Exception as err:  # noqa: BLE001 - surface any transport error
            last_err = err
            if attempt < retries:
                time.sleep(delay)
                delay *= 2
    raise RuntimeError(f"failed to download {url}: {last_err}") from last_err


def fetch(only: list[str] | None = None) -> dict:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    manifest: dict = {}
    if MANIFEST.exists():
        manifest = json.loads(MANIFEST.read_text())

    keys = only or list(SOURCES)
    failures: list[str] = []
    for key in keys:
        url, filename = SOURCES[key]
        dest = RAW_DIR / filename
        print(f"-> {key}: {url}")
        try:
            meta = _download(url, dest)
            meta["file"] = filename
            manifest[key] = meta
            print(f"   ok  {meta['bytes']:,} bytes  @ {meta['fetched_at']}")
        except Exception as err:  # noqa: BLE001
            failures.append(key)
            print(f"   FAIL {err}", file=sys.stderr)

    MANIFEST.write_text(json.dumps(manifest, indent=2))

    if failures:
        print(
            "\nSome downloads failed. In a cloud session the egress proxy may be "
            "blocking these hosts -- add 'sanctionslistservice.ofac.treas.gov' and "
            "'www.international.gc.ca' under the environment's Network access > Allowed "
            "domains, or run this fetch on a local machine.",
            file=sys.stderr,
        )
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser(description="Fetch US + Canada sanctions lists.")
    ap.add_argument(
        "--only",
        nargs="*",
        choices=list(SOURCES),
        help="fetch only these source keys (default: all)",
    )
    args = ap.parse_args()
    fetch(only=args.only)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

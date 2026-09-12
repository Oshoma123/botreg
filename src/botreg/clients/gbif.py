"""GBIF backbone taxonomy matching for botanical names.

Endpoint: https://api.gbif.org/v1/species/match?name=...

GBIF returns a `matchType` that must be preserved rather than collapsed to a
boolean:

  EXACT       the name matched a backbone name outright
  FUZZY       an approximate match; GBIF is guessing
  HIGHERRANK  GBIF could only place the name at genus or above
  NONE        no match

Only EXACT-at-species-rank-in-Plantae is treated as a species identification.
Everything else is retained with its verdict attached and reported in its own
category. Counting fuzzy and higher-rank matches as identifications is the
single easiest way to produce a species-annotated dataset that looks
authoritative and is not: a fuzzy match on a mangled label string can return
a confident-looking binomial for a plant that was never involved.

Two GBIF behaviours worth knowing:

  - `verbose=true` returns alternative candidates. When GBIF reports
    "Multiple equal matches for name" in its diagnostics, the chosen match is
    arbitrary among equals; this client records that note.
  - `strict=true` suppresses higher-rank fallback on a fuzzy match. This
    client sets it, so a failure to match a species is reported as a failure
    rather than as a genus.
"""
from __future__ import annotations

import json
import os

from ..records import TaxonMatch
from .base import BaseClient

MATCH_URL = "https://api.gbif.org/v1/species/match"
PLANTAE = "Plantae"


class GBIFClient(BaseClient):
    """Name matching against the GBIF backbone, with an on-disk cache.

    Botanical vocabularies repeat heavily across regulatory records — the
    same few hundred names account for most mentions — so caching turns a
    per-record lookup into a per-distinct-name one and makes reruns free.
    """

    def __init__(self, cache_path: str | None = None, **kwargs):
        kwargs.setdefault("min_interval", 0.2)
        super().__init__(**kwargs)
        self.cache_path = cache_path
        self._cache: dict = {}
        if cache_path and os.path.exists(cache_path):
            try:
                with open(cache_path, encoding="utf-8") as fh:
                    self._cache = json.load(fh)
            except (OSError, ValueError):
                self._cache = {}

    def save_cache(self) -> None:
        if not self.cache_path:
            return
        os.makedirs(os.path.dirname(self.cache_path) or ".", exist_ok=True)
        with open(self.cache_path, "w", encoding="utf-8") as fh:
            json.dump(self._cache, fh, indent=2, sort_keys=True)

    def match(self, name: str, kingdom: str | None = PLANTAE,
              strict: bool = True) -> TaxonMatch:
        """Match one name against the backbone.

        `kingdom` is passed as a hint, which materially improves precision:
        many botanical common names collide with animal genera, and without
        the hint GBIF will happily return one.
        """
        key = f"{name}|{kingdom}|{strict}"
        if key in self._cache:
            return _from_payload(name, self._cache[key])

        params = {"name": name, "strict": "true" if strict else "false",
                  "verbose": "true"}
        if kingdom:
            params["kingdom"] = kingdom
        payload = self.get(MATCH_URL, params, note=f"gbif match {name!r}")
        self._cache[key] = payload
        return _from_payload(name, payload)

    def match_all(self, names, kingdom: str | None = PLANTAE,
                  verbose: bool = True) -> dict:
        """Match a collection of distinct names, reporting progress."""
        names = sorted(set(n for n in names if n and n.strip()))
        out = {}
        for i, name in enumerate(names, 1):
            out[name] = self.match(name, kingdom=kingdom)
            if verbose and i % 25 == 0:
                print(f"  matched {i}/{len(names)} names", flush=True)
        self.save_cache()
        return out


def _from_payload(query_name: str, payload: dict) -> TaxonMatch:
    """Build a TaxonMatch, tolerating both the flat and nested API shapes.

    GBIF has published two response layouts: a flat one (usageKey at top
    level) and a nested one ({usage, classification, diagnostics}). Both are
    handled so a server-side change does not silently produce all-None
    annotations.
    """
    if not isinstance(payload, dict) or not payload:
        return TaxonMatch(query_name=query_name, matched=False, match_type="NONE")

    usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else None
    diagnostics = payload.get("diagnostics") if isinstance(
        payload.get("diagnostics"), dict) else None
    classification = payload.get("classification") if isinstance(
        payload.get("classification"), dict) else None

    def pick(*keys, source=None):
        for src in (source, usage, diagnostics, classification, payload):
            if not isinstance(src, dict):
                continue
            for k in keys:
                if k in src and src[k] not in (None, ""):
                    return src[k]
        return None

    match_type = str(pick("matchType") or "NONE").upper()
    rank = pick("rank")
    return TaxonMatch(
        query_name=query_name,
        matched=match_type != "NONE",
        match_type=match_type,
        usage_key=pick("usageKey", "key"),
        scientific_name=pick("scientificName"),
        canonical_name=pick("canonicalName"),
        rank=str(rank).upper() if rank else None,
        status=pick("status", "taxonomicStatus"),
        confidence=pick("confidence"),
        kingdom=pick("kingdom"),
        family=pick("family"),
        genus=pick("genus"),
        species=pick("species"),
        synonym=bool(pick("synonym") or False),
        note=pick("note"),
    )

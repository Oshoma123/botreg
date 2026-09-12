"""Botanical Adulteration Event Record (BAER) derivation.

BAER is the derived dataset: the subset of the US regulatory and label record
that mentions a botanical, with each mention annotated against the GBIF
backbone and each record classified by the kind of adulteration alleged.

What BAER is and is not
-----------------------

**It is** a reproducible index of *regulatory events that mention botanicals*,
built from primary federal and state sources, with the taxonomic verdict on
every mention preserved.

**It is not** a list of confirmed botanical adulteration incidents. A
regulatory record is an allegation, an enforcement action, or a report — not
an adjudicated finding. A 60-day notice is a private party's assertion; a
CAERS report is a spontaneous submission with no causality assessment; a
recall reason is the firm's or FDA's characterisation. BAER preserves the
source and record type on every row precisely so that a user can restrict to
the evidentiary standard they need, and no aggregate should be read as an
incident count.

Three counting rules, each of which changes the headline number
---------------------------------------------------------------

1. **One event per (record, botanical) pair.** A recall naming three
   botanicals produces three BAER events. Counting records instead would
   understate botanical involvement; counting mentions would overstate it.
   Both totals are reported.

2. **Species identification requires an EXACT GBIF match at species rank in
   Plantae.** Fuzzy and higher-rank matches are retained with their verdict
   and excluded from species-level counts.

3. **Vocabulary-limited detection.** A botanical outside the seed vocabulary
   is not detected. This is a floor on botanical involvement, never an
   estimate — `docs/LIMITATIONS.md` states it as such.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Iterable, Sequence

from .adulterant_pairs import ADULTERANT_PAIRS, PAIRS_VERSION, pairs_naming

# genus -> pairs, so a record naming only a genus still surfaces its pairs
ADULTERANT_PAIRS_BY_GENUS: dict = {}
for _p in ADULTERANT_PAIRS:
    for _s in (_p.authentic, _p.adulterant):
        if _p.adulterant_is_botanical or _s == _p.authentic:
            ADULTERANT_PAIRS_BY_GENUS.setdefault(
                _s.split()[0], []).append(_p)
from .botanicals import (VOCABULARY_VERSION, classify_adulteration,
                         find_botanicals, vocabulary_size)
from .context import CONTEXT_VERSION, classify_context
from .records import BAEREvent, RegulatoryRecord, TaxonMatch


def derive_events(records: Iterable[RegulatoryRecord],
                  taxa: dict[str, TaxonMatch] | None = None,
                  contexts: Sequence[str] | None = None
                  ) -> list[BAEREvent]:
    """Derive BAER events from regulatory records.

    `taxa` maps canonical botanical name to its GBIF verdict. When absent,
    events are emitted with `taxon=None` and reported as NOT_ATTEMPTED rather
    than as unmatched — an annotation that was never run is a different
    outcome from one that failed.
    """
    events: list[BAEREvent] = []
    keep = set(contexts) if contexts else None
    for record in records:
        text = record.searchable_text
        hits = find_botanicals(text)
        if not hits:
            continue
        if keep is not None and classify_context(text, record.source) not in keep:
            continue
        adulteration = classify_adulteration(text)
        context = classify_context(text, record.source)
        # A record naming BOTH sides of a documented adulterant pair is a
        # substitution signal, not merely a botanical mention. This is the
        # strongest evidence class BAER produces from text alone.
        present = {h.canonical for h in hits}
        signals = detect_pair_signals(present)
        for hit in hits:
            events.append(BAEREvent(
                event_id=f"{record.source}:{record.record_id}:{hit.canonical}",
                source=record.source,
                record_type=record.record_type,
                date=record.date,
                firm=record.firm,
                product_description=record.product_description,
                reason=record.reason,
                classification=record.classification,
                matched_term=hit.canonical,
                term_context=hit.context,
                adulteration_type=adulteration,
                product_context=context,
                taxon=(taxa or {}).get(hit.canonical),
                url=record.url,
                pair_signals=[sig for sig in signals
                              if hit.canonical in (sig.authentic, sig.adulterant)],
            ))
    return events


def _genus(name: str) -> str:
    return name.split()[0] if name else ""


def _side_present(species: str, present: set) -> bool:
    """Is this side of a pair represented in the record?

    Exact species match, or the genus alone. Regulatory text frequently names
    only the genus -- "contains germander", "Aristolochia species" -- and
    requiring a binomial would miss the majority of real substitution
    language. The genus match is deliberately permissive; the pair's evidence
    class and the reader's spot check carry the burden of confirmation.
    """
    if species in present:
        return True
    genus = _genus(species)
    return bool(genus) and (genus in present
                            or any(_genus(p) == genus for p in present))


def detect_pair_signals(present: set) -> list:
    """Documented adulterant pairs with BOTH sides present in one record.

    Co-occurrence is evidence of a substitution discussion, not proof of a
    substitution event: a recall notice may name both because it is reporting
    the substitution, and a product may legitimately contain both. The
    evidence class of the pair is carried through so a user can restrict to
    `documented` relationships.
    """
    signals = []
    candidates = set()
    for name in present:
        candidates.update(pairs_naming(name))
        # also consider pairs whose species share a genus with something present
        for pair in ADULTERANT_PAIRS_BY_GENUS.get(_genus(name), ()):
            candidates.add(pair)
    for pair in candidates:
        # When both sides share a genus (Curcuma longa vs Curcuma zedoaria,
        # Vaccinium myrtillus vs V. corymbosum), genus-level matching would
        # fire on any mention of the genus at all -- a record saying only
        # "turmeric" would appear to be a Curcuma substitution signal. Require
        # both binomials explicitly in that case.
        same_genus = _genus(pair.authentic) == _genus(pair.adulterant)
        if same_genus:
            ok = pair.authentic in present and pair.adulterant in present
        else:
            ok = (_side_present(pair.authentic, present)
                  and _side_present(pair.adulterant, present))
        if ok and pair not in signals:
            signals.append(pair)
    return signals


def botanicals_mentioned(records: Iterable[RegulatoryRecord]) -> list[str]:
    """Distinct canonical botanicals mentioned, for taxonomic annotation."""
    names: set[str] = set()
    for record in records:
        for hit in find_botanicals(record.searchable_text):
            names.add(hit.canonical)
    return sorted(names)


def summarise(events: Sequence[BAEREvent],
              n_records_screened: int | None = None) -> dict:
    """Summary statistics with every denominator stated.

    A percentage without its denominator is uninterpretable here: the
    plausible ones (all records screened / records mentioning a botanical /
    events / events with a species identification) differ by large factors.
    """
    n_events = len(events)
    records = {(e.source, e.event_id.rsplit(":", 1)[0]) for e in events}
    n_records_with_botanical = len(records)

    identified = [e for e in events if e.has_species_identification]
    attempted = [e for e in events if e.taxon is not None]

    match_types = Counter(
        e.taxon.match_type if e.taxon else "NOT_ATTEMPTED" for e in events)

    by_source: dict[str, dict] = defaultdict(lambda: {"events": 0, "records": set()})
    for e in events:
        bucket = by_source[e.source]
        bucket["events"] += 1
        bucket["records"].add(e.event_id.rsplit(":", 1)[0])

    canon, surfaces = vocabulary_size()
    with_signal = [e for e in events if e.pair_signals]
    documented_signal = [e for e in with_signal
                         if any(p.evidence == "documented" for p in e.pair_signals)]
    by_context = Counter(e.product_context for e in events)
    return {
        "vocabulary_version": VOCABULARY_VERSION,
        "pairs_version": PAIRS_VERSION,
        "context_version": CONTEXT_VERSION,
        "product_context": {
            "counts": dict(by_context.most_common()),
            "n_supplement": by_context.get("supplement", 0),
            "note": ("openFDA food/enforcement covers ALL food recalls, so "
                     "culinary botanicals in bread, cheese and prepared meals "
                     "are detected correctly but are not supplement "
                     "adulteration. Restrict to product_context=supplement "
                     "for the supplement population; 'ambiguous' includes "
                     "bulk botanical powders and spices"),
        },
        "pair_signals": {
            "n_events_with_pair_signal": len(with_signal),
            "n_events_with_documented_pair": len(documented_signal),
            "distinct_pairs_observed": sorted(
                {f"{p.authentic} <- {p.adulterant}"
                 for e in with_signal for p in e.pair_signals}),
            "note": ("a pair signal means one record named BOTH species of a "
                     "documented adulterant relationship; that is evidence of "
                     "a substitution discussion, not proof of a substitution "
                     "event"),
        },
        "vocabulary_size": {"canonical_botanicals": canon,
                            "surface_forms": surfaces},
        "denominator_note": (
            "events are (record, botanical) pairs, so a record naming three "
            "botanicals contributes three events; species_identified counts "
            "only EXACT GBIF matches at species rank in Plantae"),
        "n_records_screened": n_records_screened,
        "n_records_with_botanical": n_records_with_botanical,
        "pct_records_with_botanical": (
            round(100 * n_records_with_botanical / n_records_screened, 2)
            if n_records_screened else None),
        "n_events": n_events,
        "events_per_record": (round(n_events / n_records_with_botanical, 2)
                              if n_records_with_botanical else None),
        "n_distinct_botanicals": len({e.matched_term for e in events}),
        "taxonomy": {
            "n_annotation_attempted": len(attempted),
            "n_species_identified": len(identified),
            "pct_of_attempted": (round(100 * len(identified) / len(attempted), 2)
                                 if attempted else None),
            "match_type_counts": dict(match_types.most_common()),
            "note": ("only EXACT matches at species rank in Plantae count as "
                     "identifications; FUZZY and HIGHERRANK are retained but "
                     "not counted"),
        },
        "adulteration_types": dict(
            Counter(e.adulteration_type for e in events).most_common()),
        "record_types": dict(Counter(e.record_type for e in events).most_common()),
        "by_source": {src: {"n_events": v["events"],
                            "n_records": len(v["records"])}
                      for src, v in sorted(by_source.items())},
        "top_botanicals": dict(
            Counter(e.matched_term for e in events).most_common(20)),
    }


def qa_report(events: Sequence[BAEREvent], stats: dict,
              provenance_note: str, n_spot_checks: int = 4) -> str:
    """Human-readable QA report; the first thing a reader should look at."""
    L: list[str] = ["BAER QA report", "=" * 62, "",
                    f"PROVENANCE: {provenance_note}",
                    f"VOCABULARY: v{stats['vocabulary_version']} "
                    f"({stats['vocabulary_size']['canonical_botanicals']} botanicals, "
                    f"{stats['vocabulary_size']['surface_forms']} surface forms)", ""]

    L += ["SCREENING", "-" * 62]
    if stats["n_records_screened"]:
        L.append(f"  records screened:        {stats['n_records_screened']:,}")
    L += [f"  records with a botanical: {stats['n_records_with_botanical']:,}"
          + (f" ({stats['pct_records_with_botanical']}%)"
             if stats["pct_records_with_botanical"] is not None else ""),
          f"  BAER events:              {stats['n_events']:,}",
          f"  events per record:        {stats['events_per_record']}",
          f"  distinct botanicals:      {stats['n_distinct_botanicals']}",
          f"  NOTE: {stats['denominator_note']}", ""]

    ctx = stats["product_context"]
    L += ["PRODUCT CONTEXT", "-" * 62]
    for kind, n in ctx["counts"].items():
        L.append(f"  {kind}: {n:,}")
    L += [f"  NOTE: {ctx['note']}", ""]

    tax = stats["taxonomy"]
    L += ["TAXONOMIC ANNOTATION", "-" * 62,
          f"  annotation attempted:     {tax['n_annotation_attempted']:,}",
          f"  species identified:       {tax['n_species_identified']:,}"
          + (f" ({tax['pct_of_attempted']}% of attempted)"
             if tax["pct_of_attempted"] is not None else ""),
          "  match types:"]
    for mt, n in tax["match_type_counts"].items():
        L.append(f"    {mt}: {n:,}")
    L += [f"  NOTE: {tax['note']}", ""]

    L += ["ADULTERATION TYPES", "-" * 62]
    for kind, n in stats["adulteration_types"].items():
        L.append(f"  {kind}: {n:,}")

    L += ["", "BY SOURCE", "-" * 62]
    for src, v in stats["by_source"].items():
        L.append(f"  {src}: {v['n_events']:,} events from {v['n_records']:,} records")

    L += ["", "TOP BOTANICALS", "-" * 62]
    for name, n in list(stats["top_botanicals"].items())[:10]:
        L.append(f"  {name}: {n:,}")

    L += ["", "SPOT CHECKS (verify these against the source record)", "-" * 62]
    buckets: dict[str, list[BAEREvent]] = defaultdict(list)
    for e in events:
        buckets[e.adulteration_type].append(e)
    for kind in ("substitution", "contamination", "undeclared_ingredient",
                 "unspecified"):
        for e in buckets.get(kind, [])[:n_spot_checks]:
            verdict = e.taxon.match_type if e.taxon else "NOT_ATTEMPTED"
            L.append(f"  [{kind}] {e.event_id}")
            L.append(f"      term={e.matched_term} gbif={verdict} date={e.date or '-'}")
            L.append(f"      context: ...{e.term_context[:110]}...")

    L += ["", "SANITY CHECKS", "-" * 62]
    ok_events = stats["n_events"] >= stats["n_records_with_botanical"]
    L.append(f"  events >= records with a botanical: "
             f"{'PASS' if ok_events else 'FAIL (impossible)'}")
    ok_ident = tax["n_species_identified"] <= tax["n_annotation_attempted"]
    L.append(f"  identified <= attempted: {'PASS' if ok_ident else 'FAIL'}")
    total_mt = sum(tax["match_type_counts"].values())
    if total_mt == stats["n_events"]:
        L.append("  match types sum to events: PASS")
    else:
        L.append(f"  match types sum to events: FAIL "
                 f"({total_mt} match-type entries vs {stats['n_events']} events)")
    return "\n".join(L) + "\n"

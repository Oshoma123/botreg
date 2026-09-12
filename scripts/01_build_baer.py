#!/usr/bin/env python3
"""Build the Botanical Adulteration Event Record from live sources.

Requires network access. Every request is provenance-logged; the log is
written alongside the outputs so any figure can be traced to the retrieval
that produced it.

Usage:
  python scripts/01_build_baer.py --out data/processed \
      --start 2015-01-01 --end 2026-09-09 \
      --sources food_enforcement drug_enforcement food_event prop65

  # dry run against bundled fixtures, no network:
  python scripts/01_build_baer.py --fixtures tests/fixtures --out /tmp/baer

Set OPENFDA_API_KEY to raise openFDA rate limits (240/min, 120k/day with a
key; 240/min and 1,000/day without). Keys are read from the environment only
and never written to disk.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import date, datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from botreg import (DateRange, FDAAdvisoryClient, GBIFClient,  # noqa: E402
                    OpenFDAClient, Prop65Client,
                    ProvenanceLog, TruncationError, all_of, any_field_matches,
                    botanicals_mentioned, derive_events, qa_report, summarise)
from botreg.botanicals import BOTANICAL_TERMS  # noqa: E402
from botreg.records import RegulatoryRecord  # noqa: E402

SOURCES = ["food_enforcement", "drug_enforcement", "food_event",
           "prop65", "fda_advisory"]


def parse_date(text: str) -> date:
    return datetime.strptime(text, "%Y-%m-%d").date()


def botanical_clause(field: str, max_terms: int | None = None):
    """A safe disjunction over surface forms in the vocabulary.

    Built through any_field_matches so the OR is parenthesized. Constructed
    by hand this is exactly the query that triggers openFDA's OR bug and
    returns records matching only the final term.

    NOTE: with the full vocabulary this renders to roughly 30 KB, which
    exceeds what openFDA will accept in a URL. It is retained for targeted
    queries over a small term list; the default build strategy is
    fetch-broadly-and-screen-locally instead (see `fetch_openfda`).
    """
    surfaces = sorted({s for forms in BOTANICAL_TERMS.values() for s in forms})
    if max_terms:
        surfaces = surfaces[:max_terms]
    return any_field_matches(field, surfaces)


DATE_FIELD = {"food_enforcement": "report_date",
              "drug_enforcement": "report_date",
              "food_event": "date_created"}


def fetch_openfda(dataset: str, start: date, end: date, prov: ProvenanceLog,
                  max_records: int | None) -> list[RegulatoryRecord]:
    """Fetch every record in the date range, then screen locally.

    Server-side term filtering was tried first and abandoned for two reasons.
    A disjunction over the full 558-form vocabulary renders to ~30 KB, beyond
    what openFDA accepts in a URL; and openFDA's tokenizer matches on the
    analysed field, so server-side hits and local `find_botanicals` hits would
    disagree, leaving BAER's detection inconsistent with its own screening.

    The enforcement endpoints are small enough that this is cheap: ~29k food
    and ~18k drug recalls in total. Screening happens with the same code BAER
    uses downstream, so detection is consistent by construction, and
    extending the vocabulary requires no re-fetch.
    """
    client = OpenFDAClient(provenance=prov)
    date_field = DATE_FIELD[dataset]
    records: list[RegulatoryRecord] = []

    def window(y0: str, y1: str):
        return DateRange(date_field, y0, y1)

    whole = window(start.strftime("%Y%m%d"), end.strftime("%Y%m%d"))
    print(f"[{dataset}] counting records in range...", flush=True)
    total = client.count(dataset, whole)
    print(f"[{dataset}] {total:,} records in range", flush=True)
    if total == 0:
        return []

    try:
        records = list(client.fetch(dataset, whole, max_records=max_records))
    except TruncationError:
        # More records than openFDA will page through; partition by year.
        print(f"[{dataset}] exceeds the paging ceiling; fetching by year",
              flush=True)
        for year in range(start.year, end.year + 1):
            y0 = max(start, date(year, 1, 1)).strftime("%Y%m%d")
            y1 = min(end, date(year, 12, 31)).strftime("%Y%m%d")
            try:
                got = list(client.fetch(dataset, window(y0, y1),
                                        max_records=max_records))
            except TruncationError as exc:
                print(f"  {year}: STILL TRUNCATED, {exc}", flush=True)
                continue
            if got:
                print(f"  {year}: {len(got):,}", flush=True)
            records.extend(got)

    print(f"[{dataset}] retrieved {len(records):,}", flush=True)
    return records


def fetch_prop65(start: date, end: date, prov: ProvenanceLog) -> list:
    client = Prop65Client(provenance=prov)
    print("[prop65] retrieving with cap-safe bisection...", flush=True)
    records = list(client.fetch(start, end))
    print(f"[prop65] retrieved {len(records):,}", flush=True)
    return records


def cache_path(out: str, source: str) -> str:
    return os.path.join(out, "raw", f"{source}.json")


def save_cache(out: str, source: str, records: list) -> None:
    """Persist a source's records so a later failure does not discard them.

    The first production run retrieved 198,610 records from three openFDA
    endpoints and then lost all of them when a fourth source raised. Fetching
    is the expensive part; keeping it is nearly free.
    """
    path = cache_path(out, source)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump([{k: v for k, v in r.__dict__.items() if k != "raw"}
                   for r in records], fh)
    print(f"[{source}] cached {len(records):,} records to {path}", flush=True)


def load_cache(out: str, source: str) -> list | None:
    path = cache_path(out, source)
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, ValueError):
        return None
    return [RegulatoryRecord(**r) for r in raw]


def fetch_advisories(prov: ProvenanceLog, max_articles: int | None = None) -> list:
    """FDA alerts and advisories.

    Where laboratory surveillance findings surface, and therefore the only
    source in BOTREG that carries explicit botanical substitution language.
    """
    client = FDAAdvisoryClient(provenance=prov)
    print("[fda_advisory] fetching index and article bodies...", flush=True)
    records = list(client.fetch(max_articles=max_articles))
    print(f"[fda_advisory] retrieved {len(records):,}", flush=True)
    return records


def load_fixtures(path: str) -> list[RegulatoryRecord]:
    out = []
    fixture = os.path.join(path, "records.json")
    if not os.path.exists(fixture):
        sys.exit(f"no fixture at {fixture}")
    with open(fixture, encoding="utf-8") as fh:
        for raw in json.load(fh):
            out.append(RegulatoryRecord(**raw))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="data/processed")
    ap.add_argument("--start", default="2015-01-01")
    ap.add_argument("--end", default=date.today().isoformat())
    ap.add_argument("--sources", nargs="*", default=SOURCES, choices=SOURCES)
    ap.add_argument("--fixtures", help="build from local fixtures, no network")
    ap.add_argument("--max-records", type=int,
                    help="cap per source; for testing only, makes counts partial")
    ap.add_argument("--contexts", nargs="*",
                    choices=["supplement", "food", "cosmetic", "ambiguous"],
                    help="keep only these product contexts. openFDA food "
                         "enforcement covers ALL food recalls, so without a "
                         "filter the record is dominated by culinary "
                         "botanicals in bread, cheese and prepared meals, "
                         "and Prop 65 covers cosmetics too. Use "
                         "'supplement ambiguous' for the "
                         "supplement-relevant population")
    ap.add_argument("--no-cache", dest="use_cache", action="store_false",
                    help="refetch even if cached records exist")
    ap.add_argument("--no-taxonomy", action="store_true",
                    help="skip GBIF annotation (reported as NOT_ATTEMPTED)")
    a = ap.parse_args()

    os.makedirs(a.out, exist_ok=True)
    prov = ProvenanceLog()
    start, end = parse_date(a.start), parse_date(a.end)

    if a.fixtures:
        records = load_fixtures(a.fixtures)
        provenance_note = f"local fixtures at {a.fixtures} (NOT REAL DATA)"
    else:
        records = []
        succeeded, failed = [], {}
        for src in a.sources:
            if a.use_cache:
                cached = load_cache(a.out, src)
                if cached is not None:
                    print(f"[{src}] using {len(cached):,} cached records "
                          f"(--no-cache to refetch)", flush=True)
                    records += cached
                    succeeded.append(src)
                    continue
            try:
                if src == "prop65":
                    got = fetch_prop65(start, end, prov)
                elif src == "fda_advisory":
                    got = fetch_advisories(prov, a.max_records)
                else:
                    got = fetch_openfda(src, start, end, prov, a.max_records)
            except Exception as exc:                      # noqa: BLE001
                # One source failing must not discard the others. The failure
                # is recorded in the stats so a partial build is never
                # mistaken for a complete one.
                failed[src] = f"{type(exc).__name__}: {exc}"
                print(f"\n[{src}] FAILED, continuing without it:\n"
                      f"  {type(exc).__name__}: {exc}\n", flush=True)
                continue
            records += got
            succeeded.append(src)
            save_cache(a.out, src, got)

        if not records:
            sys.exit("every source failed; nothing to build")

        provenance_note = (f"live sources {', '.join(succeeded)}, "
                           f"{start} to {end}, retrieved "
                           f"{datetime.now().date().isoformat()}")
        if failed:
            provenance_note += (f" -- INCOMPLETE, failed sources: "
                                f"{', '.join(sorted(failed))}")
        if a.max_records:
            provenance_note += f" (CAPPED at {a.max_records}/source: PARTIAL)"

    print(f"\nscreening {len(records):,} records for botanicals...", flush=True)
    names = botanicals_mentioned(records)
    print(f"{len(names)} distinct botanicals mentioned", flush=True)

    taxa = {}
    if names and not a.no_taxonomy:
        print("annotating against the GBIF backbone...", flush=True)
        gbif = GBIFClient(cache_path=os.path.join(a.out, "gbif_cache.json"),
                          provenance=prov)
        taxa = gbif.match_all(names)

    events = derive_events(records, taxa, contexts=a.contexts)
    stats = summarise(events, n_records_screened=len(records))
    stats["provenance"] = provenance_note
    stats["context_filter"] = a.contexts or "none (all contexts retained)"
    if not a.fixtures:
        stats["sources_succeeded"] = succeeded
        stats["sources_failed"] = failed
        if failed:
            stats["completeness_warning"] = (
                f"BUILD IS INCOMPLETE: {', '.join(sorted(failed))} failed. "
                f"Counts below cover only {', '.join(succeeded)}.")

    rows = [e.to_row() for e in events]
    baer_path = os.path.join(a.out, "baer.csv")
    if rows:
        with open(baer_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    with open(os.path.join(a.out, "baer_stats.json"), "w", encoding="utf-8") as fh:
        json.dump(stats, fh, indent=2)
    report = qa_report(events, stats, provenance_note)
    with open(os.path.join(a.out, "baer_qa_report.txt"), "w", encoding="utf-8") as fh:
        fh.write(report)
    prov.write(os.path.join(a.out, "provenance.json"))

    print()
    print(report)
    print(f"wrote {baer_path}")
    print(f"      {a.out}/baer_stats.json")
    print(f"      {a.out}/baer_qa_report.txt")
    print(f"      {a.out}/provenance.json ({len(prov)} requests logged)")


if __name__ == "__main__":
    main()

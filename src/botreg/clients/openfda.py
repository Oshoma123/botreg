"""openFDA client: food enforcement, CAERS adverse events, drug enforcement.

Endpoints (all at https://api.fda.gov, keyless access permitted):
  /food/enforcement.json   FDA Recall Enterprise System food recalls
  /food/event.json         CAERS: food, dietary supplement and cosmetic
                           adverse event reports
  /drug/enforcement.json   RES drug recalls, which is where tainted
                           supplements marketed as drugs frequently land

Three behaviours this client exists to handle:

1. **The OR bug.** An unparenthesized OR in `search` silently discards every
   clause except the last, returning HTTP 200 with wrong records. All queries
   go through `botreg.query`, which cannot emit one.

2. **The 26,000-record skip ceiling.** openFDA refuses `skip` beyond 25,000
   and the maximum `limit` is 1,000. A query matching more than ~26,000
   records cannot be paged to completion, and naive paging stops early
   without saying so. This client detects the condition and raises
   `TruncationError` rather than returning a partial set that looks whole.
   The documented workaround is to partition by date and page each window.

3. **The empty `openfda` object.** The enrichment block is empty in every
   food record and many drug records, so it cannot be relied on for
   normalised names. This client reads the primary fields instead.
"""
from __future__ import annotations

from typing import Iterator

from ..query import build, validate_raw_query
from ..records import RegulatoryRecord
from .base import BaseClient, TruncationError, api_key

BASE = "https://api.fda.gov"
MAX_LIMIT = 1000
SKIP_CEILING = 25000          # openFDA refuses skip beyond this

ENDPOINTS = {
    "food_enforcement": ("/food/enforcement.json", "recall"),
    "food_event": ("/food/event.json", "adverse_event"),
    "drug_enforcement": ("/drug/enforcement.json", "recall"),
}


def _iso(value) -> str | None:
    """openFDA dates are YYYYMMDD strings. Normalise to ISO."""
    if not value:
        return None
    s = str(value).strip()
    if len(s) == 8 and s.isdigit():
        return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
    return s[:10] if len(s) >= 10 else s


class OpenFDAClient(BaseClient):
    """Paged access to the three openFDA endpoints BOTREG uses."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.key = api_key("OPENFDA_API_KEY")

    def count(self, dataset: str, clause=None) -> int:
        """Total records matching a query, from meta.results.total."""
        path, _ = ENDPOINTS[dataset]
        params = {"limit": 1}
        if clause is not None:
            params["search"] = self._search_value(clause)
        if self.key:
            params["api_key"] = self.key
        payload = self.get(BASE + path, params, note=f"{dataset} count")
        return int(payload.get("meta", {}).get("results", {}).get("total", 0))

    @staticmethod
    def _search_value(clause) -> str:
        """Accept a clause tree or a pre-built string, validating either."""
        if isinstance(clause, str):
            return validate_raw_query(clause)
        return build(clause)

    def fetch(self, dataset: str, clause=None, limit: int = MAX_LIMIT,
              max_records: int | None = None,
              allow_truncation: bool = False) -> Iterator[RegulatoryRecord]:
        """Page through matching records, yielding normalised records.

        Raises TruncationError if the result set exceeds what openFDA will
        page through, unless `allow_truncation=True` is passed explicitly.
        Partition by date and call once per window to cover a larger set.
        """
        path, record_type = ENDPOINTS[dataset]
        total = self.count(dataset, clause)
        if total == 0:
            return

        reachable = min(total, SKIP_CEILING + limit)
        if total > reachable and not allow_truncation and max_records is None:
            raise TruncationError(
                f"{dataset}: {total:,} records match but openFDA will only "
                f"page to ~{reachable:,} (skip ceiling {SKIP_CEILING:,}). "
                f"Returning what is reachable would understate the record "
                f"count silently. Partition the query by date and fetch each "
                f"window, or pass allow_truncation=True if a partial set is "
                f"genuinely what you want.")

        target = min(total, max_records or total, reachable)
        skip = 0
        yielded = 0
        while skip < target:
            params = {"limit": min(limit, target - skip), "skip": skip}
            if clause is not None:
                params["search"] = self._search_value(clause)
            if self.key:
                params["api_key"] = self.key
            payload = self.get(BASE + path, params,
                               note=f"{dataset} skip={skip}")
            results = payload.get("results", [])
            if not results:
                break
            for raw in results:
                yield self._to_record(dataset, record_type, raw)
                yielded += 1
            skip += len(results)

    def _to_record(self, dataset: str, record_type: str,
                   raw: dict) -> RegulatoryRecord:
        if dataset == "food_event":
            return self._caers_record(raw)
        return self._enforcement_record(dataset, record_type, raw)

    @staticmethod
    def _enforcement_record(dataset, record_type, raw) -> RegulatoryRecord:
        return RegulatoryRecord(
            record_id=str(raw.get("recall_number") or raw.get("event_id") or ""),
            source=f"openfda_{dataset}",
            record_type=record_type,
            date=_iso(raw.get("recall_initiation_date")
                      or raw.get("report_date")
                      or raw.get("center_classification_date")),
            firm=raw.get("recalling_firm"),
            product_description=raw.get("product_description"),
            reason=raw.get("reason_for_recall"),
            classification=raw.get("classification"),
            state=raw.get("state"),
            country=raw.get("country"),
            status=raw.get("status"),
            raw=raw,
        )

    @staticmethod
    def _caers_record(raw) -> RegulatoryRecord:
        """CAERS records nest products and reactions in lists.

        `products` may hold several entries; their names are joined so that
        botanical term detection sees all of them. Reactions become the
        `reason` field, since for an adverse event the reported harm is the
        analogue of a recall reason.
        """
        products = raw.get("products") or []
        names = [p.get("name_brand") for p in products if p.get("name_brand")]
        industries = {p.get("industry_name") for p in products
                      if p.get("industry_name")}
        reactions = raw.get("reactions") or []
        outcomes = raw.get("outcomes") or []
        return RegulatoryRecord(
            record_id=str(raw.get("report_number") or ""),
            source="openfda_food_event",
            record_type="adverse_event",
            date=_iso(raw.get("date_started") or raw.get("date_created")),
            firm=None,
            product_description="; ".join(names) if names else None,
            reason="; ".join(str(r) for r in reactions) if reactions else None,
            classification="; ".join(str(o) for o in outcomes) if outcomes else None,
            state=None,
            country=None,
            status="; ".join(sorted(i for i in industries if i)) or None,
            raw=raw,
        )

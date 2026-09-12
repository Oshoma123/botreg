"""California Attorney General Proposition 65 60-day notice register.

The register is the official record of every 60-day notice of violation filed
under Proposition 65, from 1988 to present, and is a primary source of
botanical adulteration signals: notices frequently name specific plant
products and the chemical alleged (commonly lead, cadmium or aristolochic
acid).

**The cap, and why it matters more than it sounds.** The AG's server-side
export returns at most 1,000 rows and has no pagination — `page` and
`items_per_page` are silently ignored. Worse, truncation drops the *newest*
rows: a broad search returns 1,000 rows ending years ago and omits everything
filed since. Read literally, a truncated result says a company has had no
notices for four years. That is the opposite of the truth, delivered without
an error.

This client never accepts a capped response. It fetches in date windows and
**bisects any window that comes back at the cap**, recursively, until every
window is provably under it. Completeness is then a property of the
retrieval, not an assumption.

Endpoint shapes change; verify against
<https://oag.ca.gov/prop65/60-day-notice-search> before a large run. This
client isolates the request construction in `_window_url` so that a change
affects one method.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterator

from ..records import RegulatoryRecord
from .base import BaseClient, FetchError, TruncationError

EXPORT_URL = "https://oag.ca.gov/prop65/60-day-notice-results-export_details.csv"
SEARCH_URL = "https://oag.ca.gov/prop65/60-day-notice-search-results"
# items_per_page and attach=page_N appear in the site's own export URLs
# but are ignored by the server; see _window_url.
ROW_CAP = 1000            # measured; the export returns no more than this
MIN_WINDOW_DAYS = 1       # a single day that still caps is a hard error


@dataclass
class Window:
    start: date
    end: date

    def halves(self) -> tuple["Window", "Window"]:
        mid = self.start + (self.end - self.start) / 2
        return Window(self.start, mid), Window(mid + timedelta(days=1), self.end)

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1

    def __str__(self) -> str:
        return f"{self.start.isoformat()}..{self.end.isoformat()}"


class Prop65Client(BaseClient):
    """Complete, cap-safe retrieval of 60-day notices."""

    def __init__(self, **kwargs):
        kwargs.setdefault("min_interval", 1.0)   # a courtesy to a state server
        super().__init__(**kwargs)

    def _window_url(self, window: Window,
                    query: str | None = None) -> tuple[str, dict]:
        """Request one date window from the CSV export.

        Pagination was tried and does not work. `items_per_page` and
        `attach=page_N` both appear in the site's own export URLs but are
        ignored: a request for 100 rows returns ~1,000, and every page
        returns the same ~1,000 rows. A first attempt to page a single year
        therefore fetched 200 identical pages before giving up.

        Date-window narrowing is the only reliable route. The window is
        bisected until every window returns under the cap, so completeness is
        established rather than assumed -- which matters more here than
        anywhere else in this package, because the register drops the NEWEST
        rows when it truncates.
        """
        params = {
            "field_prop65_report_year_value": "",
            "field_prop65_id_value": "",
            "field_prop65_plaintiff_value": "",
            "field_prop65_defendant_value": query or "",
            "field_prop65_product_value": "",
            "date_filter[min][date]": window.start.strftime("%m/%d/%Y"),
            "date_filter[max][date]": window.end.strftime("%m/%d/%Y"),
            "sort_by": "field_prop65_id_value",
        }
        return EXPORT_URL, params

    def fetch_window(self, window: Window,
                     query: str | None = None) -> list[dict]:
        """Fetch one date window. Raises TruncationError if it hits the cap."""
        url, params = self._window_url(window, query)
        payload = self.get(url, params, note=f"prop65 {window}",
                           expect_json=False)
        rows = parse_register_csv(payload)
        if len(rows) >= ROW_CAP:
            raise TruncationError(
                f"window {window} returned {len(rows):,} rows, at or above "
                f"the {ROW_CAP}-row cap. Truncation drops the NEWEST rows, so "
                f"this set is not merely short -- it is missing the most "
                f"recent notices in the window.")
        return rows

    def fetch(self, start: date, end: date, query: str | None = None,
              verbose: bool = True) -> Iterator[RegulatoryRecord]:
        """Retrieve every notice filed in the period, bisecting until complete.

        Windows are processed oldest-first so progress is legible. Every
        record yielded comes from a window that returned under the cap, so
        the set is complete for the period rather than assumed to be.
        """
        stack = [Window(start, end)]
        seen: set[str] = set()
        n_windows = 0
        columns: dict | None = None
        while stack:
            window = stack.pop()
            try:
                rows = self.fetch_window(window, query)
            except TruncationError:
                if window.days <= MIN_WINDOW_DAYS:
                    raise TruncationError(
                        f"a single day ({window.start.isoformat()}) exceeds "
                        f"the {ROW_CAP}-row cap and cannot be narrowed "
                        f"further. Do not report the period as complete.")
                left, right = window.halves()
                if verbose:
                    print(f"  {window} capped ({window.days}d); splitting",
                          flush=True)
                stack.extend([right, left])      # left popped first
                continue
            n_windows += 1
            if rows and columns is None:
                columns = self.resolve_columns(rows[0].keys())
                if verbose:
                    print("  column mapping:", flush=True)
                    for field in sorted(self.COLUMN_HINTS):
                        print(f"    {field:<12} -> "
                              f"{columns.get(field) or '(not found)'}", flush=True)
                    missing = [f for f in ("date", "firm", "chemical", "product")
                               if f not in columns]
                    if missing:
                        print(f"    WARNING: unmapped {missing}; headers were "
                              f"{sorted(rows[0].keys())}", flush=True)
            if verbose and rows:
                print(f"  {window}: {len(rows):,} notices", flush=True)
            for row in rows:
                record = self._to_record(row, columns)
                if record.record_id:
                    if record.record_id in seen:
                        continue
                    seen.add(record.record_id)
                yield record
        if verbose:
            print(f"  complete: {len(seen):,} distinct notices from "
                  f"{n_windows} windows, all under the cap", flush=True)

    # Column resolution is by substring against whatever headers arrive,
    # not by exact name. Two production runs were lost to guessed header
    # names: the first attempt mapped nothing but the AG number and the
    # comments field, which silently left product_description holding
    # amendment boilerplate and produced zero botanical detections from
    # 5,398 real notices. Substring matching survives the header renames
    # this export has already been through.
    # Header names verified against the live export 2026-09-10:
    #   AG Number | Date | Noticing Party | Plaintiff Attorney |
    #   Alleged Violator(s) | Chemicals | Source | Comments | Case ID |
    #   Case Name | Court Docket Number | Civil Penalty | Attorney Fees |
    #   Other Payments | Type of Claim | Relief Sought | Injunctive Relief
    #
    # The product column is called "Source" -- meaning source of exposure.
    # That is the single most important mapping in this client and the one
    # that is hardest to guess: it is where "La Flor Ground Oregano" lives.
    COLUMN_HINTS = {
        "record_id": ("ag_number", "ag_no", "agnumber"),
        "date": ("date_filed", "notice_date", "filed", "date"),
        "firm": ("alleged_violator", "defendant", "company", "violator"),
        "chemical": ("chemical",),
        "product": ("source_of_exposure", "product", "exposure", "source"),
        "comments": ("comment", "note"),
        "plaintiff": ("noticing_party", "plaintiff"),
        "status": ("type_of_claim", "claim", "status", "action"),
    }

    @classmethod
    def resolve_columns(cls, headers) -> dict:
        """Map logical fields to actual header names, longest hint first."""
        norm = {(h or "").strip().lower().replace(" ", "_").replace("-", "_"): h
                for h in headers or []}
        out = {}
        for field, hints in cls.COLUMN_HINTS.items():
            for hint in hints:
                exact = [k for k in norm if k == hint]
                if exact:
                    out[field] = exact[0]
                    break
                partial = sorted((k for k in norm if hint in k), key=len)
                if partial:
                    out[field] = partial[0]
                    break
        return out

    @staticmethod
    def _to_record(row: dict, columns: dict | None = None) -> RegulatoryRecord:
        if columns:
            row = {**row, **{f: row.get(col, "")
                             for f, col in columns.items() if col in row}}

        def g(*names):
            for n in names:
                v = row.get(n)
                if v:
                    return v
            return None

        # The export appends a Drupal field marker to free-text columns,
        # e.g. "...text [field_prop65_comments]". Strip it.
        product = g("product", "alleged_product", "Product")
        chemical_hint = g("chemical", "Chemical")
        comments = g("comments", "Comments") or ""
        for marker in ("[field_prop65_comments]", "[field_prop65_product]"):
            if product:
                product = product.replace(marker, "").strip()
            comments = comments.replace(marker, "").strip()

        chemical = g("chemical", "Chemical")
        return RegulatoryRecord(
            record_id=str(g("record_id", "ag_number", "ag_no", "AG Number") or ""),
            source="prop65_60day",
            record_type="notice",
            date=_iso_us(g("date", "date_filed", "noticed_date", "Date Filed")),
            firm=g("firm", "defendant", "Defendant"),
            # comments carry the substance of amendments and are searched for
            # botanical mentions alongside the product name
            product_description=" ".join(x for x in (product, comments) if x) or None,
            reason=chemical,
            classification=chemical,
            state="CA",
            country="United States",
            status=g("type_of_claim", "status", "Status"),
            raw=row,
        )


def _iso_us(value) -> str | None:
    """The register writes M/D/YYYY. Normalise to ISO."""
    if not value:
        return None
    text = str(value).strip()
    for sep in ("/", "-"):
        parts = text.split(sep)
        if len(parts) == 3 and len(parts[-1]) == 4:
            m, d, y = parts
            return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
    return text[:10]


class NotCSVError(FetchError):
    """The response was not the CSV export.

    Raised rather than parsed leniently. The AG site serves an HTML search
    page at the same paths as the export, and feeding HTML to a CSV reader
    yields rows of plausible-looking garbage rather than an error -- which is
    exactly the class of silent failure this package exists to prevent.
    """


def parse_register_csv(text: str) -> list[dict]:
    """Parse the register's CSV export into dicts with normalised keys.

    Raises NotCSVError if the payload is HTML or otherwise not the export.
    """
    import csv
    import io

    if not text or not text.strip():
        return []

    head = text.lstrip()[:400].lower()
    if head.startswith("<") or "<html" in head or "<!doctype" in head:
        raise NotCSVError(
            "the response is HTML, not the CSV export. The AG site serves a "
            "search page at this path; the export URL or its parameters have "
            "changed. Update Prop65Client._window_url -- the request "
            "construction is isolated there for exactly this reason.")

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or len(reader.fieldnames) < 2:
        raise NotCSVError(
            f"no usable CSV header; got {reader.fieldnames!r}. The endpoint "
            f"is not returning the expected export.")

    rows = []
    for raw in reader:
        row = {}
        for k, v in raw.items():
            key = (k or "").strip().lower().replace(" ", "_")
            # DictReader yields a list under the restkey when a row has more
            # fields than the header, and None when it has fewer
            if isinstance(v, list):
                v = " ".join(str(x) for x in v if x)
            row[key] = (v or "").strip() if v is not None else ""
        rows.append(row)
    return rows

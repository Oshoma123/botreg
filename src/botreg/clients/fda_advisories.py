"""FDA public health alerts, consumer advisories and safety information.

Index: <https://www.fda.gov/food/recalls-outbreaks-emergencies/alerts-advisories-safety-information>

Why this source matters
-----------------------

A build over 246,938 records from RES food and drug enforcement, CAERS and
the California Prop 65 register returned **zero** explicit botanical
substitution events — twice, under two vocabularies. Yet FDA states
substitution plainly:

    "certain dietary supplements labeled as tejocote (Crataegus mexicana)
    root are adulterated because they were tested and found to be
    substituted with yellow oleander (Cascabela thevetia)"
        -- FDA advisory, January 2024

That advisory is not a RES enforcement record, not a CAERS report and not a
Prop 65 notice. It is an alerts/advisories page, and advisories are where FDA
publishes **laboratory surveillance findings** — the results of sampling and
testing programmes, which is precisely where botanical identity failures
surface. Enforcement instruments record hazards; advisories record what the
product turned out to be.

Extraction, and its fragility
-----------------------------

There is no API. This client parses HTML, which is the least durable thing in
BOTREG: a template change on fda.gov will break it in a way no test here can
anticipate. Three defences:

* the index parse and the article parse are separate methods, so a change
  affects one;
* `parse_index` raises if it finds no advisory links at all, rather than
  returning an empty list that would read as "no advisories";
* every fetch is provenance-logged, so a run that silently degraded can be
  identified after the fact.

Only the standard library is used (`html.parser`), consistent with the rest
of the package having no runtime dependencies.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Iterator

from ..records import RegulatoryRecord
from .base import BaseClient, FetchError

INDEX_URL = ("https://www.fda.gov/food/recalls-outbreaks-emergencies/"
             "alerts-advisories-safety-information")
BASE = "https://www.fda.gov"

# Advisory links live under these path prefixes; navigation and boilerplate
# links do not.
_ADVISORY_PATH_RE = re.compile(
    r"^/(?:food|drugs|safety|consumers)/[a-z0-9\-/]+$", re.IGNORECASE)

# Titles that identify an advisory rather than a section heading.
_ADVISORY_TITLE_RE = re.compile(
    r"\b(advis|alert|warning|not to eat|stop using|public health|"
    r"consumer advice|issues warning|contaminat|recall)", re.IGNORECASE)

_MONTH_YEAR_RE = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|"
    r"October|November|December)\s+(\d{4})\b", re.IGNORECASE)

# Listing and index pages, not advisories. Scraping these is worse than
# useless: each is a table of hundreds of unrelated recalls, so a single
# "record" generates events for every product in the table and attributes
# them all to one page. A first run pulled the index page itself and the
# recalls listing, producing hits on a cranberry chicken salad sandwich.
_LISTING_SLUGS = {
    "alerts-advisories-safety-information",
    "recalls-market-withdrawals-safety-alerts",
    "recalls-outbreaks-emergencies",
    "food-safety-recalls-market-withdrawals-safety-alerts",
    "safety-recalls-market-withdrawals-safety-alerts",
    "outbreaks-foodborne-illness",
    "dietary-supplements",
    "tainted-supplements-cder",
    "medwatch-fda-safety-information-and-adverse-event-reporting-program",
    "drug-recalls",
    "enforcement-reports",
}

_MONTHS = {m.lower(): i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"], start=1)}


class _LinkExtractor(HTMLParser):
    """Collect (href, link text) pairs."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links: list = []
        self._href = None
        self._text: list = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            text = " ".join("".join(self._text).split())
            if text:
                self.links.append((self._href, text))
            self._href, self._text = None, []


class _TextExtractor(HTMLParser):
    """Strip an article to visible text, dropping script/style/nav."""

    _SKIP = {"script", "style", "nav", "header", "footer", "svg", "form"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list = []
        self._depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._depth += 1

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._depth:
            self._depth -= 1

    def handle_data(self, data):
        if not self._depth:
            text = data.strip()
            if text:
                self.parts.append(text)

    @property
    def text(self) -> str:
        return " ".join(self.parts)


def _iso_month_year(text: str) -> str | None:
    """Advisories are dated to the month: 'Updated August 2026'."""
    m = _MONTH_YEAR_RE.search(text or "")
    if not m:
        return None
    return f"{int(m.group(2)):04d}-{_MONTHS[m.group(1).lower()]:02d}-01"


class FDAAdvisoryClient(BaseClient):
    """Fetch FDA alerts and advisories, and their article text."""

    def __init__(self, **kwargs):
        kwargs.setdefault("min_interval", 1.0)   # courtesy to fda.gov
        super().__init__(**kwargs)

    def parse_index(self, html: str) -> list:
        """Extract advisory links from the index page.

        Raises rather than returning an empty list: an index that yields no
        advisories means the template changed, and reporting that as "no
        advisories exist" is the silent-failure mode this package exists to
        avoid.
        """
        parser = _LinkExtractor()
        parser.feed(html)
        seen, out = set(), []
        for href, text in parser.links:
            if not href or href.startswith(("#", "mailto:", "javascript:")):
                continue
            path = href.split("?")[0].split("#")[0]
            if path.startswith(BASE):
                path = path[len(BASE):]
            if not path.startswith("/"):
                continue
            if not _ADVISORY_PATH_RE.match(path):
                continue
            if not _ADVISORY_TITLE_RE.search(text):
                continue
            if len(text) < 25:            # section links are short
                continue
            slug = path.rstrip("/").rsplit("/", 1)[-1]
            if slug in _LISTING_SLUGS:
                continue
            if path in seen:
                continue
            seen.add(path)
            out.append({"url": BASE + path, "title": text,
                        "date": _iso_month_year(text)})
        if not out:
            raise FetchError(
                "no advisory links found on the FDA index page. The template "
                "has almost certainly changed; update "
                "FDAAdvisoryClient.parse_index rather than treating this as "
                "an absence of advisories.")
        return out

    def fetch_index(self) -> list:
        html = self.get(INDEX_URL, note="fda advisory index", expect_json=False)
        return self.parse_index(html)

    @staticmethod
    def parse_article(html: str) -> str:
        parser = _TextExtractor()
        parser.feed(html)
        return parser.text

    @staticmethod
    def article_date(text: str) -> str | None:
        """Month-precision date from the article body.

        FDA renders the date outside the anchor on the index, so link text
        usually lacks it; the article itself carries a "Content current as
        of" or a dated header. Only the first 2,000 characters are searched,
        because the page footer carries unrelated dates.
        """
        return _iso_month_year(text[:2000])

    def fetch(self, max_articles: int | None = None,
              verbose: bool = True) -> Iterator[RegulatoryRecord]:
        """Yield one record per advisory, with the article text as `reason`.

        The article body carries the substitution language; the title alone
        usually does not. Fetching bodies is therefore not optional, and is
        why this client throttles to one request per second.
        """
        entries = self.fetch_index()
        if verbose:
            print(f"  {len(entries)} advisories on the index", flush=True)
        for i, entry in enumerate(entries, 1):
            if max_articles and i > max_articles:
                break
            try:
                html = self.get(entry["url"], note=f"fda advisory {i}",
                                expect_json=False)
                body = self.parse_article(html)
            except FetchError as exc:
                if verbose:
                    print(f"    skipped {entry['url']}: {exc}", flush=True)
                continue
            if verbose and i % 20 == 0:
                print(f"    fetched {i}/{len(entries)} advisories", flush=True)
            yield RegulatoryRecord(
                record_id=entry["url"].rsplit("/", 1)[-1][:120],
                source="fda_advisory",
                record_type="advisory",
                date=entry["date"] or self.article_date(body),
                firm=None,
                product_description=entry["title"],
                # The body is where "substituted with" appears. It is long;
                # find_botanicals and classify_adulteration both handle that.
                reason=body[:20000],
                classification=None,
                state=None,
                country="United States",
                status=None,
                url=entry["url"],
                raw={"title": entry["title"], "url": entry["url"]},
            )

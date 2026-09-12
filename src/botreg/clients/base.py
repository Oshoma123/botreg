"""Shared HTTP behaviour: rate limiting, retries, and provenance logging.

Every fetch is recorded — URL, timestamp, status, record count, and a hash of
the response — so that any figure derived from a run can be traced back to
the exact request that produced it. Public agency APIs change their contents
without notice; a result that cannot be tied to a retrieval date is not
reproducible.

Rate limits (verify against each provider's current terms before a large run):
  openFDA   240 requests/min and 1,000/day without a key; 240/min and
            120,000/day with one. Set OPENFDA_API_KEY to use a key.
  GBIF      no published hard limit; this client stays well under one
            request per second by default.
  DSLD      api.data.gov backed; a key raises limits. Set DSLD_API_KEY.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone


class FetchError(RuntimeError):
    """A request failed in a way the caller must handle explicitly."""


class TruncationError(FetchError):
    """A response hit a provider cap and is therefore incomplete.

    Raised rather than returned, because a truncated result set that looks
    like a complete one is the most dangerous failure mode in this package:
    it reports fewer regulatory events than exist, which reads as evidence
    of safety.
    """


@dataclass
class ProvenanceLog:
    """Append-only record of every request made during a run."""

    entries: list = field(default_factory=list)

    def record(self, url: str, status: int, n_records: int | None,
               body_sha256: str | None, note: str = "") -> None:
        self.entries.append({
            "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "url": url,
            "http_status": status,
            "n_records": n_records,
            "body_sha256": body_sha256,
            "note": note,
        })

    def write(self, path: str) -> None:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.entries, fh, indent=2)

    def __len__(self) -> int:
        return len(self.entries)


class BaseClient:
    """Minimal HTTP client. Standard library only, so the package has no
    runtime dependencies and can run in restricted environments."""

    user_agent = "BOTREG/0.1 (+https://github.com/Oshoma123/botreg)"

    def __init__(self, min_interval: float = 0.3,
                 provenance: ProvenanceLog | None = None,
                 max_retries: int = 3, timeout: int = 60):
        self.min_interval = min_interval
        self.provenance = provenance if provenance is not None else ProvenanceLog()
        self.max_retries = max_retries
        self.timeout = timeout
        self._last_request = 0.0

    def _throttle(self) -> None:
        elapsed = time.time() - self._last_request
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last_request = time.time()

    def get(self, url: str, params: dict | None = None,
            note: str = "", expect_json: bool = True):
        """GET with retry and provenance. Returns parsed JSON or raw text."""
        if params:
            # quote_plus encodes a space as '+', which is exactly openFDA's
            # Lucene range convention: '[20040101 TO 20260909]' becomes
            # '%5B20040101+TO+20260909%5D'. An earlier version skipped
            # encoding for strings containing '+TO+', which let literal
            # spaces through and produced InvalidURL.
            query = "&".join(
                f"{k}={urllib.parse.quote_plus(str(v))}"
                for k, v in params.items() if v is not None)
            url = f"{url}?{query}"

        last_error = None
        for attempt in range(self.max_retries):
            self._throttle()
            request = urllib.request.Request(
                url, headers={"User-Agent": self.user_agent,
                              "Accept": "application/json"})
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as resp:
                    body = resp.read()
                    status = resp.status
                digest = hashlib.sha256(body).hexdigest()
                text = body.decode("utf-8", errors="replace")
                payload = json.loads(text) if expect_json else text
                n = _count_records(payload) if expect_json else None
                self.provenance.record(url, status, n, digest, note)
                return payload
            except urllib.error.HTTPError as exc:
                # 404 from openFDA means "no matches", not a failure
                if exc.code == 404:
                    self.provenance.record(url, 404, 0, None, note + " (no matches)")
                    return {"results": [], "meta": {}} if expect_json else ""
                last_error = exc
                if exc.code in (429, 500, 502, 503, 504):
                    time.sleep(2 ** attempt)
                    continue
                self.provenance.record(url, exc.code, None, None,
                                       f"{note} HTTPError {exc.code}")
                raise FetchError(f"HTTP {exc.code} for {url}") from exc
            except (urllib.error.URLError, TimeoutError, ValueError) as exc:
                last_error = exc
                time.sleep(2 ** attempt)
        self.provenance.record(url, -1, None, None, f"{note} failed after retries")
        raise FetchError(f"failed after {self.max_retries} attempts: {url}") from last_error


def _count_records(payload) -> int | None:
    if isinstance(payload, dict):
        for key in ("results", "hits", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return len(value)
        if "total" in payload:
            return payload.get("total")
    if isinstance(payload, list):
        return len(payload)
    return None


def api_key(env_var: str) -> str | None:
    """Read an API key from the environment. Keys are never written to disk."""
    return os.environ.get(env_var) or None

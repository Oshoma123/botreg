"""Safe query construction for openFDA's Lucene-backed search parameter.

openFDA has an undocumented behaviour that returns HTTP 200 with quietly
wrong data: **an unparenthesized OR discards every clause except the last
one.**

    search=classification:"Class I" OR state:"CA"
        -> returns exactly the count for state:"CA" alone
    search=state:"CA" OR classification:"Class I"
        -> returns exactly the count for classification:"Class I" alone

Nothing errors. The API returns a well-formed response of the wrong records,
and a caller who does not already know about this has no way to notice. Any
analysis built on such a query is wrong in a direction that depends on
operand order.

This module makes that mistake structurally impossible. Callers build queries
from `Term` and the combinators `all_of` / `any_of`, which emit correctly
parenthesized Lucene, rather than assembling strings by hand.
`validate_raw_query` is provided for the case where a raw string must be
accepted (a CLI flag, a config file) and refuses unparenthesized ORs.

Field values are quoted and escaped, so a botanical name containing a space
or a hyphen cannot silently become two terms.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence

# Lucene special characters that must be escaped inside a quoted phrase.
_ESCAPE_RE = re.compile(r'([+\-!(){}\[\]^"~*?:\\/])')

# A bare OR (or lowercase 'or' used as an operator) not inside parentheses.
_BARE_OR_RE = re.compile(r'(?<![\w"])(?:OR|\|\|)(?![\w"])')


class UnsafeQueryError(ValueError):
    """Raised for a query shape known to return silently wrong results."""


def escape_value(value: str) -> str:
    """Escape a value for use inside a quoted Lucene phrase."""
    return _ESCAPE_RE.sub(r"\\\1", value)


@dataclass(frozen=True)
class Term:
    """A single `field:"value"` clause.

    Values are always quoted. openFDA's tokenizer splits unquoted multi-word
    values, so `product_description:Ginkgo biloba` silently becomes a search
    for `Ginkgo` plus a stray token, matching far more than intended.
    """

    field: str
    value: str
    exact: bool = False   # append .exact for the non-analysed subfield

    def render(self) -> str:
        field = f"{self.field}.exact" if self.exact else self.field
        return f'{field}:"{escape_value(self.value)}"'


@dataclass(frozen=True)
class DateRange:
    """An inclusive date range on an openFDA date field (YYYYMMDD)."""

    field: str
    start: str
    end: str

    def render(self) -> str:
        # A literal space; the HTTP layer encodes it as '+', which is
        # openFDA's range convention. Embedding '+' here would double-encode.
        return f"{self.field}:[{self.start} TO {self.end}]"


Clause = "Term | DateRange | _Group"


@dataclass(frozen=True)
class _Group:
    op: str                      # "AND" or "OR"
    parts: tuple

    def render(self) -> str:
        if not self.parts:
            raise UnsafeQueryError("empty group would match everything")
        if len(self.parts) == 1:
            return self.parts[0].render()
        joined = f" {self.op} ".join(p.render() for p in self.parts)
        # Parentheses are what make OR behave. They are not optional and are
        # not a stylistic choice; see the module docstring.
        return f"({joined})"


def all_of(*parts) -> _Group:
    """Conjunction. Always parenthesized."""
    return _Group("AND", tuple(parts))


def any_of(*parts) -> _Group:
    """Disjunction. Always parenthesized -- this is the whole point.

    Building an OR by string concatenation is the documented way to get
    silently wrong results out of openFDA, so this is the only supported
    way to express one.
    """
    return _Group("OR", tuple(parts))


def build(clause) -> str:
    """Render a clause tree to an openFDA `search` parameter value."""
    rendered = clause.render()
    validate_raw_query(rendered)
    return rendered


def validate_raw_query(query: str) -> str:
    """Reject query strings whose OR clauses are not parenthesized.

    Used on raw user-supplied queries (CLI, config). Scans left to right
    tracking parenthesis depth; any OR seen at depth zero is unsafe, because
    at depth zero openFDA will drop everything before it.
    """
    depth = 0
    in_quote = False
    i = 0
    while i < len(query):
        ch = query[i]
        if ch == "\\":
            i += 2
            continue
        if ch == '"':
            in_quote = not in_quote
        elif not in_quote:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth < 0:
                    raise UnsafeQueryError(f"unbalanced parentheses: {query!r}")
            elif depth == 0:
                m = _BARE_OR_RE.match(query, i)
                if m:
                    raise UnsafeQueryError(
                        "unparenthesized OR at top level. openFDA silently "
                        "discards every clause except the last one, returning "
                        "HTTP 200 with the wrong records. Wrap the disjunction "
                        f"in parentheses, or use any_of(). Query: {query!r}")
        i += 1
    if depth != 0:
        raise UnsafeQueryError(f"unbalanced parentheses: {query!r}")
    if in_quote:
        raise UnsafeQueryError(f"unterminated quote: {query!r}")
    return query


def any_field_matches(field: str, values: Sequence[str], exact: bool = False) -> _Group:
    """`field` matches any of `values` -- the common safe-OR case.

    A bare string is rejected rather than accepted. Python would iterate it
    character by character, so `any_field_matches("reactions", "NAUSEA")`
    would build a six-clause OR over single letters and return a plausible
    but meaningless result set. That is the same failure mode as the OR bug
    itself: no error, wrong answer.
    """
    if isinstance(values, (str, bytes)):
        raise UnsafeQueryError(
            f"values must be a sequence of strings, not a bare string "
            f"({values!r}). Python would iterate it character by character, "
            f"silently building an OR over single letters. Pass [{values!r}].")
    values = list(values)
    if not values:
        raise UnsafeQueryError("no values given; an empty OR matches everything")
    return any_of(*(Term(field, v, exact=exact) for v in values))

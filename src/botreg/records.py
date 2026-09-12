"""Unified record shapes across the six sources.

Each source has its own schema, vocabulary and date format. Downstream code
(BAER derivation, taxonomy annotation, reporting) works on these types and
never needs to know which agency a record came from.

Dates are normalised to ISO `YYYY-MM-DD` on ingest, because the sources use
at least three conventions (openFDA `YYYYMMDD`, DSLD ISO timestamps, the CA
AG register `M/D/YYYY`) and comparing them as raw strings sorts incorrectly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RegulatoryRecord:
    """One record from any regulatory or enforcement source."""

    record_id: str
    source: str            # openfda_food_enforcement | openfda_food_event |
                           # openfda_drug_enforcement | fda_warning_letter |
                           # prop65_60day | dsld_label
    record_type: str       # recall | adverse_event | warning_letter | notice | label
    date: str | None = None            # ISO YYYY-MM-DD
    firm: str | None = None
    product_description: str | None = None
    reason: str | None = None          # recall reason / violation / allegation
    classification: str | None = None  # Class I/II/III, or notice chemical
    state: str | None = None
    country: str | None = None
    status: str | None = None
    url: str | None = None
    raw: dict = field(default_factory=dict)

    @property
    def searchable_text(self) -> str:
        """Concatenated free text used for botanical term detection."""
        parts = [self.product_description, self.reason, self.firm]
        return " ".join(p for p in parts if p)


@dataclass
class TaxonMatch:
    """Result of matching a botanical name against the GBIF backbone.

    `match_type` is GBIF's own verdict and must be preserved, not collapsed
    to a boolean. EXACT is an identification; FUZZY is a suggestion; HIGHERRANK
    means GBIF could only place the name at genus or above; NONE is a failure.
    Treating the last three as identifications is the central way a
    species-annotated dataset becomes quietly wrong.
    """

    query_name: str
    matched: bool
    match_type: str                    # EXACT | FUZZY | HIGHERRANK | NONE
    usage_key: int | None = None
    scientific_name: str | None = None
    canonical_name: str | None = None
    rank: str | None = None
    status: str | None = None          # ACCEPTED | SYNONYM | DOUBTFUL ...
    confidence: int | None = None
    kingdom: str | None = None
    family: str | None = None
    genus: str | None = None
    species: str | None = None
    synonym: bool = False
    note: str | None = None

    @property
    def is_species_level_identification(self) -> bool:
        """True only for an EXACT match resolved to species rank.

        This is the conservative criterion BAER uses for its headline
        species counts. Anything else is retained and reported in its own
        category rather than counted as an identification.
        """
        return (self.matched
                and self.match_type == "EXACT"
                and self.rank == "SPECIES"
                and self.kingdom == "Plantae")


@dataclass
class BAEREvent:
    """One Botanical Adulteration Event Record entry.

    A regulatory record that mentions a botanical, with the botanical term
    that triggered it and the taxonomic verdict on that term.
    """

    event_id: str
    source: str
    record_type: str
    date: str | None
    firm: str | None
    product_description: str | None
    reason: str | None
    classification: str | None
    matched_term: str                  # the botanical term found in the text
    term_context: str                  # surrounding text, for verification
    adulteration_type: str             # substitution | contamination |
                                       # undeclared_ingredient | mislabeling |
                                       # unapproved_ingredient | unspecified
    product_context: str = "ambiguous" # supplement | food | ambiguous
    taxon: TaxonMatch | None = None
    url: str | None = None
    pair_signals: list = field(default_factory=list)

    @property
    def has_species_identification(self) -> bool:
        return bool(self.taxon and self.taxon.is_species_level_identification)

    def to_row(self) -> dict[str, Any]:
        t = self.taxon
        return {
            "event_id": self.event_id,
            "source": self.source,
            "record_type": self.record_type,
            "date": self.date or "",
            "firm": self.firm or "",
            "product_description": self.product_description or "",
            "reason": self.reason or "",
            "classification": self.classification or "",
            "matched_term": self.matched_term,
            "term_context": self.term_context,
            "adulteration_type": self.adulteration_type,
            "product_context": self.product_context,
            "gbif_match_type": t.match_type if t else "NOT_ATTEMPTED",
            "gbif_usage_key": t.usage_key if t and t.usage_key else "",
            "gbif_scientific_name": t.scientific_name if t else "",
            "gbif_rank": t.rank if t else "",
            "gbif_status": t.status if t else "",
            "gbif_confidence": t.confidence if t and t.confidence is not None else "",
            "gbif_family": t.family if t else "",
            "gbif_genus": t.genus if t else "",
            "species_identified": self.has_species_identification,
            "pair_signal": ";".join(
                f"{p.authentic}<-{p.adulterant}" for p in self.pair_signals),
            "pair_evidence": ";".join(
                sorted({p.evidence for p in self.pair_signals})),
            "pair_mode": ";".join(sorted({p.mode for p in self.pair_signals})),
            "url": self.url or "",
        }

"""BOTREG: unified programmatic access to the US public regulatory and label
record for dietary supplements, and BAER, the Botanical Adulteration Event
Record derived from it.

Sources: NIH Dietary Supplement Label Database; openFDA food enforcement,
CAERS adverse events and drug enforcement; FDA warning letters; California
Proposition 65 60-day notices. Botanical mentions are annotated against the
GBIF taxonomic backbone.
"""
__version__ = "0.1.0"

from .query import (Term, DateRange, all_of, any_of, any_field_matches, build,
                    validate_raw_query, UnsafeQueryError)
from .records import RegulatoryRecord, TaxonMatch, BAEREvent
from .botanicals import (find_botanicals, classify_adulteration,
                         vocabulary_size, VOCABULARY_VERSION)
from .context import CONTEXT_VERSION, classify_context, is_supplement_context
from .baer import (derive_events, botanicals_mentioned, summarise, qa_report,
                   detect_pair_signals)
from .adulterant_pairs import (ADULTERANT_PAIRS, AdulterantPair, PAIRS_VERSION,
                               pairs_for, pairs_naming)
from .clients import (OpenFDAClient, Prop65Client, GBIFClient, Window,
                      FDAAdvisoryClient,
                      ProvenanceLog, FetchError, TruncationError)

__all__ = [
    "__version__",
    "Term", "DateRange", "all_of", "any_of", "any_field_matches", "build",
    "validate_raw_query", "UnsafeQueryError",
    "RegulatoryRecord", "TaxonMatch", "BAEREvent",
    "find_botanicals", "classify_adulteration", "vocabulary_size",
    "VOCABULARY_VERSION",
    "derive_events", "botanicals_mentioned", "summarise", "qa_report",
    "detect_pair_signals", "classify_context", "is_supplement_context",
    "CONTEXT_VERSION", "ADULTERANT_PAIRS", "AdulterantPair",
    "PAIRS_VERSION", "pairs_for", "pairs_naming",
    "OpenFDAClient", "Prop65Client", "GBIFClient", "Window",
    "FDAAdvisoryClient",
    "ProvenanceLog", "FetchError", "TruncationError",
]

"""Tests for BOTREG.

The heaviest coverage is on the three behaviours that produce silently wrong
answers rather than errors: the openFDA OR bug, the Prop 65 row cap, and
GBIF match-quality collapse. Those are the failures a user cannot see.
"""
import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from botreg.baer import derive_events, botanicals_mentioned, summarise  # noqa: E402
from botreg.botanicals import (classify_adulteration, find_botanicals,  # noqa: E402
                               vocabulary_size)
from botreg.clients.gbif import _from_payload  # noqa: E402
from botreg.clients.openfda import _iso  # noqa: E402
from botreg.clients.prop65 import Window, _iso_us, parse_register_csv  # noqa: E402
from botreg.query import (DateRange, Term, UnsafeQueryError, all_of,  # noqa: E402
                          any_field_matches, any_of, build, escape_value,
                          validate_raw_query)
from botreg.records import RegulatoryRecord, TaxonMatch  # noqa: E402


# ============================================================ query safety

def test_or_is_always_parenthesized():
    """The core guarantee. openFDA drops every clause but the last when an
    OR is unparenthesized, returning HTTP 200 with wrong records."""
    q = build(any_of(Term("classification", "Class I"), Term("state", "CA")))
    assert q.startswith("(") and q.endswith(")")
    assert " OR " in q


def test_raw_query_with_bare_or_is_rejected():
    for bad in ['a:"1" OR b:"2"',
                'a:"1" || b:"2"',
                '(a:"1" OR b:"2") OR c:"3"',
                'x:"1" AND y:"2" OR z:"3"']:
        try:
            validate_raw_query(bad)
        except UnsafeQueryError:
            continue
        raise AssertionError(f"unsafe query not rejected: {bad}")


def test_parenthesized_or_is_accepted():
    assert validate_raw_query('(a:"1" OR b:"2") AND c:"3"')
    assert validate_raw_query('a:"1" AND (b:"2" OR c:"3")')


def test_or_inside_a_quoted_value_is_not_an_operator():
    """A product literally named 'SALT OR PEPPER' must not trip the guard."""
    assert validate_raw_query('product_description:"SALT OR PEPPER"')


def test_values_are_quoted_so_multiword_terms_stay_one_term():
    """Unquoted, openFDA tokenizes 'Ginkgo biloba' into two terms and matches
    far more than intended."""
    assert build(Term("product_description", "Ginkgo biloba")) == \
        'product_description:"Ginkgo biloba"'


def test_special_characters_are_escaped():
    assert "\\-" in escape_value("ma-huang")
    assert "\\:" in escape_value("a:b")


def test_bare_string_rejected_where_sequence_expected():
    """Python would iterate the string character by character, silently
    building an OR over single letters."""
    try:
        any_field_matches("reactions", "NAUSEA")
    except UnsafeQueryError:
        return
    raise AssertionError("bare string accepted; would OR over single letters")


def test_empty_disjunction_rejected():
    for call in (lambda: build(any_of()), lambda: any_field_matches("f", [])):
        try:
            call()
        except UnsafeQueryError:
            continue
        raise AssertionError("empty OR accepted; would match everything")


def test_nested_clause_renders_correctly():
    q = build(all_of(Term("status", "Ongoing"),
                     any_of(Term("classification", "Class I"),
                            Term("classification", "Class II"))))
    assert q == ('(status:"Ongoing" AND (classification:"Class I" '
                 'OR classification:"Class II"))')


def test_date_range_renders_with_a_literal_space():
    """The '+' in openFDA's documented '[a+TO+b]' is an encoded space.
    Emitting a literal '+' here and then URL-encoding produces '%2BTO%2B',
    which openFDA does not parse as a range."""
    assert build(DateRange("report_date", "20200101", "20261231")) == \
        "report_date:[20200101 TO 20261231]"


def test_date_range_encodes_to_openfda_wire_format():
    import urllib.parse
    rendered = build(DateRange("report_date", "20200101", "20261231"))
    encoded = urllib.parse.quote_plus(rendered)
    assert "+TO+" in encoded
    assert "%2BTO%2B" not in encoded


def test_full_vocabulary_disjunction_is_too_large_for_a_url():
    """Documents why the build screens locally rather than server-side: the
    full vocabulary rendered as an OR exceeds any practical URL length."""
    from botreg.botanicals import BOTANICAL_TERMS
    surfaces = sorted({f for forms in BOTANICAL_TERMS.values() for f in forms})
    rendered = build(any_field_matches("product_description", surfaces))
    assert len(rendered) > 20000


def test_unbalanced_parentheses_rejected():
    for bad in ['(a:"1"', 'a:"1")', '((a:"1")']:
        try:
            validate_raw_query(bad)
        except UnsafeQueryError:
            continue
        raise AssertionError(f"unbalanced parens accepted: {bad}")


# ====================================================== date normalisation

def test_openfda_dates_normalised_to_iso():
    assert _iso("20260314") == "2026-03-14"
    assert _iso(None) is None


def test_prop65_us_dates_normalised_to_iso():
    assert _iso_us("3/14/2026") == "2026-03-14"
    assert _iso_us("12/1/2020") == "2020-12-01"
    assert _iso_us(None) is None


# ============================================================ prop 65 caps

def test_export_url_uses_date_window_not_pagination():
    """Two production failures are pinned here. The URL was first a guess
    that returned the HTML search page; the second attempt used
    items_per_page and attach=page_N, which the site publishes in its own
    export links but the server ignores -- a request for 100 rows returns
    ~1,000, and every page returns the same rows. Date windowing is the only
    route that terminates."""
    from botreg.clients.prop65 import EXPORT_URL, Prop65Client, Window
    url, params = Prop65Client()._window_url(Window(date(2024, 1, 1),
                                                    date(2024, 6, 30)))
    assert url == EXPORT_URL and url.endswith(".csv")
    assert params["date_filter[min][date]"] == "01/01/2024"
    assert params["date_filter[max][date]"] == "06/30/2024"
    assert "attach" not in params and "items_per_page" not in params


def test_html_response_raises_rather_than_parsing_garbage():
    """Feeding the HTML search page to a CSV reader yields plausible-looking
    rows rather than an error -- the exact silent failure this guards."""
    from botreg.clients.prop65 import NotCSVError
    for payload in ("<!DOCTYPE html><html><body>results</body></html>",
                    "<html><head><title>60-Day Notice Search</title></head>"):
        try:
            parse_register_csv(payload)
        except NotCSVError:
            continue
        raise AssertionError("HTML parsed as CSV")


def test_rows_with_extra_fields_do_not_crash():
    """csv.DictReader yields a list under the restkey when a row has more
    fields than the header; the first production run crashed on this."""
    rows = parse_register_csv(
        "AG Number,Date Filed\n2026-1,5/2/2026,extra,fields\n")
    assert rows and rows[0]["ag_number"] == "2026-1"


def test_columns_resolved_by_substring_not_exact_name():
    """Two production runs were lost to guessed header names. The second
    mapped only the AG number and comments, so product_description held
    amendment boilerplate and 5,398 real notices produced zero botanical
    detections. Substring resolution survives header renames."""
    from botreg.clients.prop65 import Prop65Client
    cols = Prop65Client.resolve_columns(
        ["AG Number", "Date Filed", "Plaintiff", "Defendant", "Chemical",
         "Product", "Comments"])
    assert cols["record_id"] == "ag_number"
    assert cols["date"] == "date_filed"
    assert cols["firm"] == "defendant"
    assert cols["chemical"] == "chemical"
    assert cols["product"] == "product"


LIVE_PROP65_HEADERS = [
    "AG Number", "Date", "Noticing Party", "Plaintiff Attorney",
    "Alleged Violator(s)", "Chemicals", "Source", "Comments", "Case ID",
    "Case Name", "Court Docket Number", "Civil Penalty", "Attorney Fees",
    "Other Payments", "Type of Claim", "Relief Sought", "Injunctive Relief",
]


def test_live_headers_all_resolve():
    """Verified against the live export 2026-09-10. The product column is
    called 'Source' (source of exposure) -- the hardest mapping to guess and
    the one whose absence produced zero detections from 5,398 notices."""
    from botreg.clients.prop65 import Prop65Client
    cols = Prop65Client.resolve_columns(LIVE_PROP65_HEADERS)
    assert cols["record_id"] == "ag_number"
    assert cols["date"] == "date"
    assert cols["firm"] == "alleged_violator(s)"
    assert cols["chemical"] == "chemicals"
    assert cols["product"] == "source"
    assert cols["status"] == "type_of_claim"


def test_live_header_record_yields_a_botanical_event():
    """The full path with the real header names and a real notice."""
    from botreg.clients.prop65 import Prop65Client
    cols = Prop65Client.resolve_columns(LIVE_PROP65_HEADERS)
    rec = Prop65Client._to_record({
        "ag_number": "2023-03895", "date": "12/08/2023",
        "alleged_violator(s)": "La Flor Products Company, Inc.",
        "chemicals": "Lead", "source": "La Flor Ground Oregano",
        "type_of_claim": "Failure to Warn"}, cols)
    assert rec.date == "2023-12-08" and rec.reason == "Lead"
    events = derive_events([rec])
    assert events and events[0].matched_term == "Origanum vulgare"
    assert events[0].adulteration_type == "contamination"


def test_column_resolution_survives_renamed_headers():
    from botreg.clients.prop65 import Prop65Client
    cols = Prop65Client.resolve_columns(
        ["AG No.", "Notice Date", "Noticing Party", "Alleged Violator",
         "Chemical", "Source of Exposure", "Type of Claim"])
    assert cols["date"] == "notice_date"
    assert cols["firm"] == "alleged_violator"
    assert cols["product"] == "source_of_exposure"


def test_resolved_columns_populate_the_record():
    from botreg.clients.prop65 import Prop65Client
    headers = ["AG Number", "Date Filed", "Defendant", "Chemical", "Product"]
    cols = Prop65Client.resolve_columns(headers)
    rec = Prop65Client._to_record({
        "ag_number": "2023-03895", "date_filed": "12/08/2023",
        "defendant": "La Flor Products Company, Inc.", "chemical": "Lead",
        "product": "La Flor Ground Oregano"}, cols)
    assert rec.date == "2023-12-08"
    assert rec.firm.startswith("La Flor")
    assert rec.reason == "Lead"
    assert "Oregano" in rec.product_description


def test_resolved_prop65_record_yields_a_botanical():
    """End to end: the exact record shape that returned zero detections."""
    from botreg.clients.prop65 import Prop65Client
    cols = Prop65Client.resolve_columns(
        ["AG Number", "Date Filed", "Defendant", "Chemical", "Product"])
    rec = Prop65Client._to_record({
        "ag_number": "2023-03895", "date_filed": "12/08/2023",
        "defendant": "La Flor Products Company, Inc.", "chemical": "Lead",
        "product": "La Flor Ground Oregano"}, cols)
    events = derive_events([rec])
    assert events and events[0].matched_term == "Origanum vulgare"
    assert events[0].adulteration_type == "contamination"


def test_drupal_field_markers_stripped_from_free_text():
    from botreg.clients.prop65 import Prop65Client
    rec = Prop65Client._to_record({
        "ag_number": "2023-03895", "date_filed": "12/08/2023",
        "defendant": "La Flor Products Company, Inc.", "chemical": "Lead",
        "product": "La Flor Ground Oregano",
        "comments": "This notice amends the previous notice. [field_prop65_comments]"})
    assert "[field_prop65" not in (rec.product_description or "")
    assert "Oregano" in rec.product_description
    assert rec.reason == "Lead" and rec.state == "CA"


def test_window_bisects_toward_single_days():
    w = Window(date(2020, 1, 1), date(2020, 12, 31))
    left, right = w.halves()
    assert left.start == w.start and right.end == w.end
    assert left.end < right.start                 # no overlap
    assert left.days + right.days == w.days       # no gap


def test_window_bisection_terminates():
    w = Window(date(2020, 1, 1), date(2020, 1, 4))
    for _ in range(10):
        if w.days <= 1:
            break
        w, _r = w.halves()
    assert w.days == 1


def test_register_csv_parsed_with_normalised_keys():
    rows = parse_register_csv(
        "AG Number,Date Filed,Defendant,Product,Chemical\n"
        "2026-01234,5/2/2026,Supplement Corp,Ashwagandha powder,Lead\n")
    assert rows[0]["ag_number"] == "2026-01234"
    assert rows[0]["chemical"] == "Lead"


def test_empty_register_response_is_empty_not_error():
    assert parse_register_csv("") == []


# ==================================================== botanical detection

def test_detects_binomial_and_common_forms():
    assert find_botanicals("Ginkgo Biloba capsules")[0].canonical == "Ginkgo biloba"
    assert find_botanicals("ma huang extract")[0].canonical == "Ephedra sinica"


def test_longer_term_wins_over_shorter():
    """'Siberian ginseng' is Eleutherococcus, not Panax."""
    hits = find_botanicals("Siberian Ginseng blend")
    assert [h.canonical for h in hits] == ["Eleutherococcus senticosus"]


def test_word_boundaries_prevent_substring_matches():
    assert find_botanicals("Aloeswood incense") == []
    assert find_botanicals("Gingerbread cookies") == []


def test_firm_names_are_not_botanicals():
    """Over-detection on brand names would contaminate the record invisibly."""
    assert find_botanicals("Nature's Bounty Hair Skin Nails") == []


def test_one_hit_per_canonical_botanical():
    hits = find_botanicals("Ginkgo and Ginkgo biloba and ginko")
    assert len(hits) == 1


def test_multiple_distinct_botanicals_all_found():
    hits = find_botanicals("Turmeric and Ashwagandha and Kratom blend")
    assert {h.canonical for h in hits} == {
        "Curcuma longa", "Withania somnifera", "Mitragyna speciosa"}


def test_context_is_captured_for_verification():
    hit = find_botanicals("Recall of Turmeric powder due to lead")[0]
    assert "Turmeric" in hit.context


def test_vocabulary_is_non_trivial():
    canonical, surfaces = vocabulary_size()
    assert canonical >= 30 and surfaces >= canonical


# ================================================ adulteration classification

def test_fda_adulterated_is_not_read_as_substitution():
    """'Adulterated' is a legal term of art under FD&C Act 402 meaning broadly
    non-compliant. Reading it as species substitution would inflate exactly
    the figure this dataset exists to report."""
    assert classify_adulteration(
        "Product adulterated with undeclared sildenafil") == "undeclared_ingredient"
    assert classify_adulteration(
        "Adulterated product, elevated lead levels") == "contamination"


def test_explicit_substitution_language_is_classified():
    for text in ("Skullcap substituted with germander",
                 "DNA barcoding showed a different species",
                 "plant material was not the declared botanical"):
        assert classify_adulteration(text) == "substitution", text


def test_unstated_problem_is_unspecified_not_guessed():
    assert classify_adulteration("Voluntary recall, packaging defect") == "unspecified"
    assert classify_adulteration("") == "unspecified"


# ============================================================ GBIF verdicts

def _tm(match_type, rank="SPECIES", kingdom="Plantae"):
    return TaxonMatch(query_name="X", matched=match_type != "NONE",
                      match_type=match_type, rank=rank, kingdom=kingdom)


def test_only_exact_species_plantae_counts_as_identification():
    assert _tm("EXACT").is_species_level_identification
    assert not _tm("FUZZY").is_species_level_identification
    assert not _tm("HIGHERRANK", rank="GENUS").is_species_level_identification
    assert not _tm("NONE").is_species_level_identification
    assert not _tm("EXACT", kingdom="Animalia").is_species_level_identification
    assert not _tm("EXACT", rank="GENUS").is_species_level_identification


def test_gbif_flat_payload_parsed():
    m = _from_payload("Ginkgo biloba", {
        "usageKey": 5285750, "scientificName": "Ginkgo biloba L.",
        "rank": "SPECIES", "status": "ACCEPTED", "confidence": 99,
        "matchType": "EXACT", "kingdom": "Plantae", "family": "Ginkgoaceae"})
    assert m.usage_key == 5285750 and m.match_type == "EXACT"
    assert m.is_species_level_identification


def test_gbif_nested_payload_parsed():
    """GBIF has published both layouts; a server-side change must not
    silently produce all-None annotations."""
    m = _from_payload("Ginkgo biloba", {
        "usage": {"key": 5285750, "canonicalName": "Ginkgo biloba",
                  "rank": "SPECIES", "status": "ACCEPTED"},
        "classification": {"kingdom": "Plantae", "family": "Ginkgoaceae"},
        "diagnostics": {"matchType": "EXACT", "confidence": 99}})
    assert m.match_type == "EXACT" and m.kingdom == "Plantae"
    assert m.is_species_level_identification


def test_gbif_empty_payload_is_none_match():
    assert _from_payload("Nonsense", {}).match_type == "NONE"
    assert not _from_payload("Nonsense", {}).matched


# =================================================== BAER derivation & stats

def _rec(rid, desc, reason, source="openfda_food_enforcement"):
    return RegulatoryRecord(rid, source, "recall", date="2026-01-01",
                            firm="F", product_description=desc, reason=reason)


def test_records_without_botanicals_are_excluded():
    events = derive_events([_rec("1", "Salted crackers", "Undeclared milk")])
    assert events == []


def test_one_event_per_record_botanical_pair():
    events = derive_events([_rec("1", "Turmeric and Ashwagandha", "Lead")])
    assert len(events) == 2
    assert {e.matched_term for e in events} == {"Curcuma longa", "Withania somnifera"}


def test_event_ids_are_unique_and_traceable():
    events = derive_events([_rec("1", "Turmeric and Ashwagandha", "Lead")])
    assert len({e.event_id for e in events}) == 2
    assert all(e.event_id.startswith("openfda_food_enforcement:1:") for e in events)


def test_missing_taxonomy_is_not_attempted_not_unmatched():
    """An annotation never run is a different outcome from one that failed."""
    events = derive_events([_rec("1", "Turmeric", "Lead")])
    assert events[0].taxon is None
    assert events[0].to_row()["gbif_match_type"] == "NOT_ATTEMPTED"
    assert summarise(events)["taxonomy"]["match_type_counts"] == {"NOT_ATTEMPTED": 1}


def test_fuzzy_match_excluded_from_species_counts_but_retained():
    taxa = {"Curcuma longa": _tm("FUZZY")}
    events = derive_events([_rec("1", "Turmeric", "Lead")], taxa)
    stats = summarise(events)
    assert stats["taxonomy"]["n_species_identified"] == 0
    assert stats["taxonomy"]["match_type_counts"] == {"FUZZY": 1}
    assert events[0].to_row()["gbif_match_type"] == "FUZZY"


def test_summary_denominators_are_stated_and_consistent():
    taxa = {"Curcuma longa": _tm("EXACT"), "Withania somnifera": _tm("FUZZY")}
    events = derive_events([
        _rec("1", "Turmeric and Ashwagandha", "Lead"),
        _rec("2", "Plain crackers", "Undeclared milk")], taxa)
    stats = summarise(events, n_records_screened=2)
    assert stats["n_records_screened"] == 2
    assert stats["n_records_with_botanical"] == 1
    assert stats["n_events"] == 2
    assert stats["taxonomy"]["n_species_identified"] == 1
    assert sum(stats["taxonomy"]["match_type_counts"].values()) == stats["n_events"]
    assert "denominator_note" in stats


def test_botanicals_mentioned_returns_sorted_distinct_names():
    names = botanicals_mentioned([_rec("1", "Turmeric", "x"),
                                  _rec("2", "turmeric powder", "y"),
                                  _rec("3", "Kratom", "z")])
    assert names == ["Curcuma longa", "Mitragyna speciosa"]


def test_events_span_multiple_sources():
    events = derive_events([
        _rec("1", "Turmeric", "Lead"),
        _rec("2", "Kratom", "Nausea", source="openfda_food_event"),
        _rec("3", "Ashwagandha", "Lead", source="prop65_60day")])
    assert len(summarise(events)["by_source"]) == 3


# ================================================== adulterant pair signals

from botreg.adulterant_pairs import (ADULTERANT_PAIRS, AdulterantPair,  # noqa: E402
                                     EVIDENCE_CLASSES, SUBSTITUTION_MODES,
                                     adulterant_species, authentic_species,
                                     pairs_naming, summary)
from botreg.baer import detect_pair_signals  # noqa: E402
from botreg.botanicals import BOTANICAL_TERMS  # noqa: E402


def test_pair_table_is_substantial_and_well_formed():
    s = summary()
    assert s["n_pairs"] >= 80
    assert s["n_authentic_species"] >= 60
    assert all(p.mode in SUBSTITUTION_MODES for p in ADULTERANT_PAIRS)
    assert all(p.evidence in EVIDENCE_CLASSES for p in ADULTERANT_PAIRS)


def test_evidence_classes_are_not_collapsed():
    """'plausible' leads must remain distinguishable from documented cases."""
    s = summary()
    assert s["by_evidence"]["documented"] > 0
    assert "plausible" in s["by_evidence"]


def test_invalid_mode_or_evidence_rejected():
    for kwargs in ({"mode": "nonsense", "evidence": "documented"},
                   {"mode": "substitution", "evidence": "certain"}):
        try:
            AdulterantPair("A", "B", **kwargs)
        except ValueError:
            continue
        raise AssertionError(f"invalid pair accepted: {kwargs}")


def test_every_pair_species_is_detectable():
    """A pair whose species are absent from the vocabulary can never fire."""
    needed = set()
    for p in ADULTERANT_PAIRS:
        needed.add(p.authentic)
        if p.adulterant_is_botanical:
            needed.add(p.adulterant)
    assert not (needed - set(BOTANICAL_TERMS))


def test_documented_hepatotoxic_pairs_present():
    """The two best-established toxic substitutions in the literature."""
    assert any(p.adulterant.startswith("Teucrium")
               for p in pairs_naming("Scutellaria lateriflora"))
    assert any(p.adulterant.startswith("Aristolochia")
               for p in pairs_naming("Stephania tetrandra"))


def test_pair_signal_requires_both_sides():
    assert detect_pair_signals({"Scutellaria lateriflora"}) == []
    assert detect_pair_signals({"Teucrium canadense"}) == []
    assert detect_pair_signals(
        {"Scutellaria lateriflora", "Teucrium canadense"}) != []


def test_genus_only_mention_still_signals_across_genera():
    """Regulatory text often names only the genus: 'contains germander'."""
    assert detect_pair_signals({"Scutellaria lateriflora", "Teucrium"}) != []


def test_same_genus_pairs_require_both_binomials():
    """Otherwise any mention of 'turmeric' would look like a Curcuma
    substitution signal, since Curcuma longa and C. zedoaria share a genus."""
    assert detect_pair_signals({"Curcuma longa"}) == []
    assert detect_pair_signals({"Curcuma longa", "Curcuma zedoaria"}) != []


def test_pair_signals_recorded_on_events():
    recs = [_rec("1", "Skullcap capsules", "contains germander, hepatotoxicity")]
    events = derive_events(recs)
    assert any(e.pair_signals for e in events)
    row = [e for e in events if e.pair_signals][0].to_row()
    assert "Teucrium" in row["pair_signal"]
    assert row["pair_evidence"] == "documented"


def test_summary_reports_pair_signals_separately():
    events = derive_events([
        _rec("1", "Skullcap", "contains germander"),
        _rec("2", "Turmeric", "elevated lead")])
    stats = summarise(events, n_records_screened=2)
    assert stats["pair_signals"]["n_events_with_pair_signal"] >= 1
    assert stats["pair_signals"]["n_events_with_documented_pair"] >= 1
    assert "note" in stats["pair_signals"]
    assert "pairs_version" in stats


def test_vocabulary_expanded_and_covers_trade():
    canonical, surfaces = vocabulary_size()
    assert canonical >= 180, canonical
    assert surfaces >= 450, surfaces


def test_non_botanical_adulterants_flagged():
    """Lead chromate and synthetic yohimbine are not species and must not be
    sent to GBIF as if they were."""
    non_bot = [p for p in ADULTERANT_PAIRS if not p.adulterant_is_botanical]
    assert len(non_bot) >= 8
    assert all(p.adulterant not in adulterant_species() for p in non_bot)



# ========================================================= product context

from botreg.context import classify_context, is_supplement_context  # noqa: E402


def test_prepared_foods_classified_as_food():
    """The first live run over 500 food recalls surfaced cinnamon bagels,
    garlic cheddar, artichoke dip and cranberry cookie dough. Each detection
    is correct and each is irrelevant to supplement adulteration."""
    for text in ("Cinnamon Raisin Bagels: gluten-free cinnamon raisin bagels",
                 "Face Rock Creamery Vampire Slayer Garlic Cheddar",
                 "Spinach Artichoke Dip (Sold Hot) 1 lb",
                 "CraftMark Oatmeal Cranberry Raisin Cookie Dough"):
        assert classify_context(text) == "food", text


def test_dosage_forms_classified_as_supplement():
    for text in ("Ginkgo Biloba Extract 120mg capsules, dietary supplement",
                 "Ashwagandha root powder, 60 vegcaps",
                 "Turmeric Curcumin with Bioperine, Supplement Facts"):
        assert classify_context(text) == "supplement", text


def test_bulk_botanical_is_ambiguous_not_guessed():
    """Bulk powders and spices genuinely are ambiguous; saying so is more
    honest than assigning them to either population."""
    assert classify_context("Organic Moringa Powder; 15kg/bag (bulk)") == "ambiguous"
    assert classify_context("Ground Cinnamon 7oz jars; elevated lead") == "ambiguous"


def test_supplement_marker_outranks_food_marker():
    """Supplement bars and functional beverages carry both."""
    assert classify_context(
        "Protein snack bar, dietary supplement, Supplement Facts") == "supplement"


def test_dsld_records_are_supplements_by_source():
    assert classify_context("", source="dsld_label") == "supplement"


def test_empty_text_is_ambiguous():
    assert classify_context("") == "ambiguous"


def test_context_recorded_on_events_and_summarised():
    events = derive_events([
        _rec("1", "Ginkgo capsules, dietary supplement", "undeclared sildenafil"),
        _rec("2", "Cinnamon Raisin Bagels", "undeclared milk allergen")])
    contexts = {e.product_context for e in events}
    assert "supplement" in contexts and "food" in contexts
    stats = summarise(events, n_records_screened=2)
    assert stats["product_context"]["n_supplement"] >= 1
    assert "note" in stats["product_context"]
    assert events[0].to_row()["product_context"] in {"supplement", "food", "ambiguous"}


def test_context_filter_excludes_food():
    recs = [_rec("1", "Ginkgo capsules, dietary supplement", "undeclared drug"),
            _rec("2", "Cinnamon Raisin Bagels", "undeclared milk")]
    supplement_only = derive_events(recs, contexts=["supplement"])
    assert all(e.product_context == "supplement" for e in supplement_only)
    assert len(supplement_only) < len(derive_events(recs))


def test_is_supplement_context_helper():
    assert is_supplement_context("dietary supplement capsules")
    assert not is_supplement_context("cinnamon bagels")



def test_cosmetics_classified_separately():
    """A live Prop 65 run over 5,398 notices surfaced aloe vera gel, tea tree
    peel-off masks, aloe sheet masks and shave foam -- all Diethanolamine
    notices on cosmetics. Prop 65 covers all consumer products, and
    botanicals are ubiquitous in personal care."""
    for text in ("Signature Care aloe vera gel Diethanolamine",
                 "Precision Beauty Tea Tree peel-off masks Diethanolamine",
                 "aloe sheet masks Diethanolamine",
                 "Signature Care lotion with aloe, shave foam"):
        assert classify_context(text) == "cosmetic", text


def test_supplement_outranks_cosmetic():
    """'softgel' contains 'gel'; the supplement patterns are tested first."""
    assert classify_context("Ginkgo Biloba 120mg softgels") == "supplement"
    assert classify_context("Turmeric gel caps, Supplement Facts") == "supplement"


def test_botanical_powders_remain_ambiguous():
    """The real supplement signals from Prop 65 are terse product names with
    no dosage form. Calling them 'supplement' would overstate; calling them
    'food' would be wrong. Ambiguous is the honest answer."""
    assert classify_context("Peruvian Naturals Organic Maca Lead") == "ambiguous"
    assert classify_context(
        "Ashwagandha Maca Root, Turmeric Curcumin Powder Lead") == "ambiguous"


# ============================== substitution: the tejocote correction

def test_fda_tejocote_advisory_classifies_as_substitution():
    """The first production run reported ZERO substitution events and the
    findings claimed the US regulatory record never states substitution.
    That was wrong. FDA's January 2024 advisory says products labelled
    tejocote root were 'tested and found to be substituted with yellow
    oleander'. Neither species was in the vocabulary, so those records were
    undetectable rather than misclassified.
    """
    text = ("FDA analysis has determined that certain dietary supplements "
            "labeled as tejocote (Crataegus mexicana) root are adulterated "
            "because they were tested and found to be substituted with "
            "yellow oleander (Cascabela thevetia), a poisonous plant.")
    found = {h.canonical for h in find_botanicals(text)}
    assert "Crataegus mexicana" in found
    assert "Cascabela thevetia" in found
    assert classify_adulteration(text) == "substitution"


def test_tejocote_pair_is_documented_and_fires():
    from botreg.adulterant_pairs import pairs_naming
    pairs = pairs_naming("Crataegus mexicana")
    assert any(p.adulterant == "Cascabela thevetia" and p.evidence == "documented"
               for p in pairs)
    signals = detect_pair_signals({"Crataegus mexicana", "Cascabela thevetia"})
    assert signals


def test_toxic_substitute_species_are_detectable():
    """Species that appear as adulterants in poisoning cases must be in the
    vocabulary or the substitution can never be seen."""
    for name in ("yellow oleander", "japanese star anise", "aconite",
                 "belladonna", "foxglove", "colchicine", "germander"):
        assert find_botanicals(f"product contained {name}"), name


# ==================================== plant-part substitution (21 CFR 101.36)

def test_plant_part_substitution_is_a_distinct_class():
    """21 CFR 101.36(b)(3) requires the plant part to be declared, and
    21 USC 343(s)(2)(C) makes a supplement misbranded if it is not. Species
    identity and plant-part identity are separate regulatory failures."""
    for text in ("Ashwagandha product used leaf material instead of root",
                 "kava made with stem peelings rather than root",
                 "leaf powder in place of root extract",
                 "labeling fails to identify the plant part"):
        assert classify_adulteration(text) == "plant_part_substitution", text


def test_species_substitution_outranks_plant_part():
    """A record stating species substitution is classified as such even if it
    also names plant parts."""
    assert classify_adulteration(
        "tejocote root substituted with yellow oleander") == "substitution"


# ================================================= FDA alerts and advisories

from botreg.clients.fda_advisories import (FDAAdvisoryClient,  # noqa: E402
                                           _iso_month_year)

INDEX_HTML = """<html><body>
<a href="/food/alerts-advisories-safety-information/fda-issues-warning-toxic-yellow-oleander">FDA Issues Warning About Certain Products Containing Toxic Yellow Oleander Updated August 2026</a>
<a href="/food/alerts-advisories-safety-information/ground-cinnamon-public-health-alert">More Ground Cinnamon Products Added to FDA Public Health Alert Due to Presence of Elevated Levels of Lead November 2025</a>
<a href="/about-fda">About FDA</a>
<a href="#skip-to-main">Skip to main content</a>
<a href="mailto:x@fda.gov">Contact</a>
</body></html>"""


def test_index_extracts_advisories_and_rejects_navigation():
    entries = FDAAdvisoryClient().parse_index(INDEX_HTML)
    assert len(entries) == 2
    urls = " ".join(e["url"] for e in entries)
    assert "yellow-oleander" in urls
    assert "about-fda" not in urls


def test_index_dates_parsed_to_month_precision():
    """Advisories are dated to the month: 'Updated August 2026'."""
    entries = {e["title"][:20]: e["date"]
               for e in FDAAdvisoryClient().parse_index(INDEX_HTML)}
    assert "2026-08-01" in entries.values()
    assert "2025-11-01" in entries.values()
    assert _iso_month_year("no date here") is None


def test_empty_index_raises_rather_than_reporting_no_advisories():
    """A template change must not read as 'FDA has issued no advisories'."""
    from botreg.clients.base import FetchError
    for html in ("<html><body><a href='/about-fda'>About</a></body></html>",
                 "<html><body>nothing</body></html>"):
        try:
            FDAAdvisoryClient().parse_index(html)
        except FetchError:
            continue
        raise AssertionError("empty index accepted silently")


def test_article_text_strips_script_style_and_nav():
    html = ("<html><head><style>.a{color:red}</style></head><body>"
            "<nav>Menu Home Search</nav><p>Real advisory text.</p>"
            "<script>track()</script></body></html>")
    text = FDAAdvisoryClient.parse_article(html)
    assert "Real advisory text." in text
    assert "color:red" not in text and "track()" not in text and "Menu" not in text


def test_advisory_article_yields_a_substitution_event():
    """The whole point of adding this source: the tejocote advisory carries
    explicit substitution language that no enforcement endpoint does."""
    html = ("<html><body><p>FDA analysis has determined that certain dietary "
            "supplements labeled as tejocote (Crataegus mexicana) root are "
            "adulterated because they were tested and found to be substituted "
            "with yellow oleander (Cascabela thevetia), a poisonous "
            "plant.</p></body></html>")
    text = FDAAdvisoryClient.parse_article(html)
    assert classify_adulteration(text) == "substitution"
    rec = RegulatoryRecord(
        "fda-tejocote", "fda_advisory", "advisory", date="2024-01-01",
        product_description="Tejocote root supplements", reason=text)
    events = derive_events([rec])
    terms = {e.matched_term for e in events}
    assert {"Crataegus mexicana", "Cascabela thevetia"} <= terms
    assert all(e.adulteration_type == "substitution" for e in events)
    assert any(e.pair_signals for e in events)


def test_listing_pages_are_not_treated_as_advisories():
    """A first live run scraped the index page itself and the recalls
    listing. Each is a table of hundreds of unrelated recalls, so one
    'record' generated events for every product in the table -- including a
    cranberry chicken salad sandwich. Listing slugs are excluded."""
    html = """<html><body>
    <a href="/food/alerts-advisories-safety-information/fda-issues-warning-toxic-yellow-oleander">FDA Issues Warning About Certain Products Containing Toxic Yellow Oleander Updated August 2026</a>
    <a href="/food/recalls-outbreaks-emergencies/alerts-advisories-safety-information">Alerts, Advisories and Safety Information page</a>
    <a href="/safety/recalls-market-withdrawals-safety-alerts">Recalls, Market Withdrawals and Safety Alerts listing</a>
    </body></html>"""
    entries = FDAAdvisoryClient().parse_index(html)
    slugs = {e["url"].rsplit("/", 1)[-1] for e in entries}
    assert "fda-issues-warning-toxic-yellow-oleander" in slugs
    assert "alerts-advisories-safety-information" not in slugs
    assert "recalls-market-withdrawals-safety-alerts" not in slugs


def test_article_body_supplies_the_date_when_the_link_text_lacks_it():
    """FDA renders the date outside the anchor, so most links carry none."""
    assert FDAAdvisoryClient.article_date(
        "FDA Issues Warning. Content current as of January 2024.") == "2024-01-01"
    assert FDAAdvisoryClient.article_date("no date anywhere here") is None


def test_real_advisory_language_classifies_as_substitution():
    """The exact wording returned by the live tejocote advisory."""
    text = ("FDA analysis has determined that certain products labeled as "
            "tejocote (Crataegus mexicana) root or Brazil seed are "
            "adulterated because they contain yellow oleander (Thevetia "
            "peruviana) instead of the labeled ingredient.")
    assert classify_adulteration(text) == "substitution"
    found = {h.canonical for h in find_botanicals(text)}
    assert "Crataegus mexicana" in found
    assert "Cascabela thevetia" in found      # Thevetia peruviana synonym

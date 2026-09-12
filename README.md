# BOTREG and BAER

**BOTREG** is an open-source package providing unified programmatic access to
the United States public regulatory and label record for dietary supplements.
**BAER**, the Botanical Adulteration Event Record, is the dataset derived from
it: regulatory events that mention a botanical, annotated against the GBIF
taxonomic backbone.

Founded September 2026.
Maintainer: Oshoma Erumiseli ([ORCID 0009-0004-3813-4650](https://orcid.org/0009-0004-3813-4650)).
Code [MIT](LICENSE) · BAER dataset [CC0 1.0](LICENSE-DATA).

## Status: first full production run complete

Engine finished and tested (86 tests, CI on Python 3.9 and 3.12). **BAER v1
has been built from live sources**: 247,005 US regulatory records screened
across all five endpoints, 2004–2026, producing 11,636 botanical events.

**Findings: [`docs/BAER_FINDINGS.md`](docs/BAER_FINDINGS.md)**

| Measure | Value |
|---|---|
| Records screened | 247,005 |
| Records mentioning a botanical | 9,803 (3.97%) |
| BAER events | 11,636 |
| Distinct botanicals | 160 |
| Species-level GBIF identification | 83.54% of attempted |
| Explicit substitution events | **3**, all from advisories |

### The headline result

**All 3 species-substitution events in BAER come from FDA advisories. None
come from the 246,938 enforcement, adverse-event and Prop 65 records.**

| Source | Records | Substitution events |
|---|---|---|
| openFDA food + drug enforcement | 47,324 | 0 |
| openFDA CAERS | 151,286 | 0 |
| CA Prop 65 register | 48,328 | 0 |
| **FDA alerts & advisories** | **67** | **3** |

Advisories are 0.027% of the corpus and supply 100% of the substitution
signal. The result survived a control: an earlier run added precisely the
species from the best-documented US case — *Crataegus mexicana*, *Cascabela
thevetia* — to the vocabulary, re-screened the identical corpus, and still
returned zero. That eliminated the vocabulary as the explanation and isolated
source coverage. Adding advisories made the count non-zero immediately.

**Why:** enforcement instruments record *hazards*; advisories record *what
the product turned out to be*. A recall states a hazard and a remedy, a
Prop 65 notice names a chemical, a CAERS report records a symptom — none has
a convention for "the plant in this product was not the plant on the label",
even when that is what prompted the action. Advisories are the publication
route for laboratory surveillance, and identity findings surface where
testing programmes report.

**Consequence:** a botanical adulteration record drawn from enforcement
endpoints alone will report zero substitution, and the zero will be an
artifact of source selection.

**Three events, one finding.** All three trace to the same advisory, counted
separately because it names three terms. Two are species-level GBIF
identifications on the sentence that states the substitution; the third,
"Brazil seed", is a commercial name with no taxon and its context is a
product table. The honest statement is *one substitution finding, three
events, two species-level*.

Three events is also a floor, not a market estimate — the index carries 67
current advisories, not a complete history. Full account in
[`docs/BAER_FINDINGS.md`](docs/BAER_FINDINGS.md) §1.

### Other results

**Kratom leads at 1,034 events (9.0%)**, ahead of cinnamon and cannabis,
despite having no food use — driven by adverse event reports rather than
recalls.

**70.0% of events come from CAERS**, the source with no causality assessment.
Recalls, the only type carrying an agency determination, are 13.2%. Any
aggregate not restricted by `record_type` is dominated by self-reported data.

**Co-occurrence is a weak substitution proxy.** 62 events name both sides of a
documented adulterant pair, but inspection shows most are ingredient lists
(saffron and turmeric in a spice blend), not substitution reports.

**The complete California Prop 65 register** was retrieved: 48,328 notices
across 22 years in 98 windows, every one provably under the 1,000-row cap.

## Sources## Sources

| Source | What it provides | Licence | Verified |
|---|---|---|---|
| [NIH DSLD](https://dsld.od.nih.gov) | 200,000+ supplement labels, ingredients, claims | CC0 1.0 | 2026-09-09 |
| [openFDA food enforcement](https://open.fda.gov/apis/food/enforcement/) | FDA RES food recalls, 2004– | US Gov work | 2026-09-09 |
| [openFDA CAERS](https://open.fda.gov/apis/food/event/) | Food, supplement and cosmetic adverse events | US Gov work | 2026-09-09 |
| [openFDA drug enforcement](https://open.fda.gov/apis/drug/enforcement/) | RES drug recalls, where tainted supplements often land | US Gov work | 2026-09-09 |
| [FDA alerts & advisories](https://www.fda.gov/food/recalls-outbreaks-emergencies/alerts-advisories-safety-information) | Laboratory surveillance findings — **where substitution appears** | US Gov work | 2026-09-10 |
| FDA warning letters | Enforcement correspondence — *not yet implemented* | US Gov work | 2026-09-09 |
| [CA AG Prop 65 register](https://oag.ca.gov/prop65/60-day-notice-search) | 60-day notices of violation, 1988– | CA public record | 2026-09-09 |
| [GBIF backbone](https://api.gbif.org) | Taxonomic annotation of botanical names | CC BY 4.0 | 2026-09-09 |

## Why this package exists: three silent failure modes

Each of these returns a plausible, well-formed, **wrong** answer. None raises
an error. A researcher who does not already know about them has no way to
notice, and every one of them biases results toward *understating* regulatory
activity — which reads as evidence of safety.

**1. openFDA drops all but the last clause of an unparenthesized OR.**

```
search=classification:"Class I" OR state:"CA"   → the count for state:"CA" alone
search=state:"CA" OR classification:"Class I"   → the count for classification alone
```

HTTP 200 both times. BOTREG makes this impossible: queries are built from
`Term`/`any_of`/`all_of`, which always parenthesize, and raw query strings are
rejected by `validate_raw_query` if they contain a top-level OR.

**2. The Prop 65 register caps at 1,000 rows and truncates the newest first.**

`page` and `items_per_page` are silently ignored. A broad search returns 1,000
rows ending years ago and omits everything filed since — read literally, that
a company has been clear for four years. `Prop65Client` treats any response at
the cap as a hard error and **bisects the date window** until every window is
provably under it, so completeness is a property of the retrieval rather than
an assumption.

**3. GBIF fuzzy matches look like identifications.**

`matchType` may be `EXACT`, `FUZZY`, `HIGHERRANK` or `NONE`. A fuzzy match on
a mangled label string returns a confident-looking binomial for a plant that
was never involved. BOTREG counts **only** EXACT matches at species rank in
Plantae as identifications, retains the others with their verdict attached,
and reports the match-type breakdown in every summary.

## Install and run

```bash
pip install -e ".[dev]"
pytest tests/ -v                    # 86 tests, Python 3.9+

# Build BAER from bundled fixtures (offline, proves the pipeline):
python scripts/01_build_baer.py --fixtures tests/fixtures --out /tmp/baer --no-taxonomy

# Real build:
export OPENFDA_API_KEY=...          # optional, raises rate limits
python scripts/01_build_baer.py --out data/processed \
    --start 2015-01-01 --end 2026-09-09
```

Library use:

```python
from botreg import OpenFDAClient, Term, all_of, DateRange, any_field_matches

client = OpenFDAClient()
query = all_of(
    DateRange("report_date", "20200101", "20261231"),
    any_field_matches("product_description", ["ginkgo", "ma huang"]),
)
for record in client.fetch("food_enforcement", query):
    print(record.date, record.firm, record.product_description)
```

## What BAER is, and is not

**It is** a reproducible index of regulatory events that *mention* botanicals,
built from primary sources, with the taxonomic verdict on every mention
preserved and the source and record type on every row.

**It is not** a list of confirmed adulteration incidents. A recall reason is a
characterisation; a 60-day notice is a private party's assertion; a CAERS
report is a spontaneous submission with no causality assessment. Restrict to
the evidentiary standard you need — the columns are there for exactly that —
and do not read any aggregate as an incident count.

## Product context: the filter you almost certainly want

openFDA's `food/enforcement` endpoint covers **all** food recalls, not just
supplements. A first live run over 500 records returned, among its most
frequent botanicals, *Cinnamomum* from cinnamon raisin bagels, *Allium
sativum* from garlic cheddar, *Cynara scolymus* from spinach artichoke dip,
and *Vaccinium macrocarpon* from oatmeal cranberry cookie dough.

Every one of those detections is correct, and every one is irrelevant to
botanical adulteration in supplements. Unfiltered, BAER would be a list of
baked goods.

BOTREG classifies rather than discards, because a lead-contaminated turmeric
*spice* is genuinely relevant even though it is not a supplement:

| Context | Meaning |
|---|---|
| `supplement` | Explicit supplement language or dosage form (capsule, softgel, Supplement Facts) |
| `food` | Prepared-food language |
| `cosmetic` | Personal-care language — Prop 65 covers all consumer products, and a live run returned aloe gel, tea tree masks and shave foam |
| `ambiguous` | None of the above — bulk botanical powders and spices land here, honestly |

```bash
# the supplement-relevant population:
python scripts/01_build_baer.py --out data/processed --contexts supplement ambiguous
```

Classification is conservative: `supplement` requires a positive marker, so
that population is a floor rather than an estimate. Every event carries its
context, and the summary reports the counts, so the size of the food
population is visible rather than hidden.

## Counting rules

Three rules, each of which changes the headline number, so each is stated
rather than assumed:

1. **One event per (record, botanical) pair.** A recall naming three
   botanicals yields three events. Both event and record totals are reported.
2. **Species identification requires EXACT + species rank + Plantae.**
3. **Detection is vocabulary-limited** (v0.1.0: 209 botanicals, 558 surface
   forms). Anything outside it is missed, so botanical involvement is a
   **floor, never an estimate**.
4. **A pair signal is not a substitution event.** A record naming both sides
   of a documented adulterant pair is evidence of a substitution *discussion*
   — the notice may be reporting the substitution, or the product may
   legitimately contain both.

## Adulterant pairs

BAER does not only detect that a record mentions a botanical; it detects when
a record names **both sides of a documented adulterant relationship**.
`src/botreg/adulterant_pairs.py` encodes 88 pairs covering
78 authentic species — germander for American
skullcap, *Aristolochia fangchi* for *Stephania tetrandra*, *Periploca sepium*
for eleuthero, cassia for Ceylon cinnamon, safflower for saffron, and so on.

Each pair carries a substitution mode (admixture, chemical_spiking, misidentification, substitution), an
evidence class, the plant part, why it matters, and the analytical methods
that distinguish the two. Evidence classes are **not** collapsed:

| Class | Meaning | Count |
|---|---|---|
| `documented` | Established in analytical literature, pharmacopoeial monographs, or regulatory action | 36 |
| `reported` | Reported, with less analytical confirmation | 28 |
| `plausible` | Named as a concern in review literature; a lead, not a finding | 24 |

12 adulterants are non-botanical (lead
chromate in turmeric, synthetic yohimbine, metanil yellow) and are flagged so
they are never sent to GBIF as if they were species.

**Verify before citing.** Pairs were compiled from domain literature and
carry an evidence class, but citations are not machine-verified. Treat
`plausible` entries as leads.

## Layout

```
src/botreg/
  query.py         safe openFDA query construction (the OR guard)
  records.py       unified record types across all sources
  botanicals.py    botanical vocabulary, detection, adulteration classification
  adulterant_pairs.py  documented adulterant-authentic species pairs
  context.py       supplement vs food product-context classification
  baer.py          BAER derivation, summary statistics, QA report
  clients/         base (HTTP, provenance), openfda, prop65, gbif
scripts/           01_build_baer.py
tests/             76 tests + offline fixtures
docs/              LIMITATIONS, VOCABULARY, SOURCES
```

## Limitations

See [`docs/LIMITATIONS.md`](docs/LIMITATIONS.md) before citing anything.

## Citation

See `CITATION.cff`. A DOI will be minted on the first release.

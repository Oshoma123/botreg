# BAER v1: the first full production run

**247,005 US regulatory records screened; 11,636 botanical events indexed.**

| | |
|---|---|
| Sources | openFDA food enforcement (29,386) · drug enforcement (17,938) · CAERS (151,286) · CA Prop 65 (48,328) · FDA alerts & advisories (67) |
| Period | 2004-01-01 to 2026-09-09 |
| Context filter | `supplement`, `ambiguous` — food and cosmetic excluded |
| Vocabulary | v0.2.1, 229 botanicals / 610 surface forms |
| Run | 2026-09-10, BOTREG v0.9, 698 requests logged |

Data: `data/processed/baer_stats_2026.09.json`, `baer.csv`, `provenance.json`.

```
python scripts/01_build_baer.py --out data/processed \
  --start 2004-01-01 --end 2026-09-09 --contexts supplement ambiguous
```

---

## Headline

| Measure | Value |
|---|---|
| Records screened | 247,005 |
| Records mentioning a botanical | 9,803 (**3.97%**) |
| BAER events (record × botanical) | **11,636** |
| Distinct botanicals | 160 of 229 in the vocabulary |
| Species-level GBIF identification | 9,721 (**83.54%** of attempted) |
| Explicit **substitution** events | **0** |

---

## 1. Substitution appears only in advisories

**All 3 species-substitution events in BAER come from FDA advisories. None
come from the 246,938 enforcement, adverse-event and Prop 65 records.**

| Source | Records | Substitution events |
|---|---|---|
| openFDA food enforcement | 29,386 | 0 |
| openFDA drug enforcement | 17,938 | 0 |
| openFDA CAERS | 151,286 | 0 |
| CA Prop 65 register | 48,328 | 0 |
| **FDA alerts & advisories** | **67** | **3** |

Advisories are **0.027% of the corpus and supply 100% of the substitution
signal.** All three events trace to one advisory — the tejocote case — in
which FDA states:

> "certain products labeled as tejocote (*Crataegus mexicana*) root or Brazil
> seed are adulterated because they contain yellow oleander (*Thevetia
> peruviana*) **instead of the labeled** ingredient"

### How this was established

The result survived two attempts to explain it away:

| Run | Sources | Vocabulary | Events | Substitution |
|---|---|---|---|---|
| 1 | 4 (no advisories) | v0.1.0, 209 botanicals | 11,478 | 0 |
| 2 | 4 (no advisories) | v0.2.0, 229 botanicals | 11,636 | 0 |
| 3 | **5 (with advisories)** | v0.2.1, 229 botanicals | 11,636 | **3** |

Run 2 was the control. It added precisely the species from the
best-documented US substitution case — *Crataegus mexicana*, *Cascabela
thevetia*, and the toxic substitutes that recur in poisoning literature — and
re-screened the identical corpus. **Still zero.** That eliminated the
vocabulary as the explanation and isolated source coverage.

Run 3 added the advisories client and the count became non-zero immediately.

### Why the record is shaped this way

Enforcement instruments record **hazards**; advisories record **what the
product turned out to be**.

A recall states a hazard and a remedy. A Prop 65 notice names a listed
chemical. A CAERS report records a symptom. None of these has a field, a
convention, or an evidentiary need for the finding "the plant in this product
was not the plant on the label" — even when that finding is what prompted the
action. The tejocote products were recalled, and the recall records describe
the hazard (cardiac glycosides) rather than the identity failure.

Advisories are different because they are the publication route for
**laboratory surveillance**: FDA sampled nine products, ran DNA and chemical
analysis, and published what the analysis found. Identity findings surface
where testing programmes report, and essentially nowhere else in the public
record.

**Consequence for anyone building on regulatory data:** a botanical
adulteration record drawn from enforcement endpoints alone will report zero
substitution and the zero will be an artifact of source selection. BAER
measures contamination and undeclared ingredients well from enforcement
sources; substitution requires advisories, import alerts, and ultimately the
laboratory surveillance literature.

### Three events, one finding

The three events are verified and all trace to the **same advisory**. Under
BAER's one-event-per-(record, botanical) rule they count as three because the
advisory names three terms:

| Event | GBIF verdict | Context |
|---|---|---|
| *Crataegus mexicana* | EXACT, *Crataegus mexicana* Moc. & Sessé ex DC. | the substitution sentence |
| *Cascabela thevetia* | EXACT, *Cascabela thevetia* (L.) Lippold | the substitution sentence |
| "Brazil seed" | **NONE** | a product table, not the substitution sentence |

Two are species-level identifications on the sentence that states the
substitution. The third is weaker on both counts: "Brazil seed" is a
commercial name with no taxon behind it, and its surrounding text is the
affected-products table rather than the finding.

**The honest statement is therefore: one substitution finding, three events,
two species-level.** Reporting "3 substitution events" without that
decomposition would let the event-counting rule carry more weight than the
evidence does.

Advisory dates came through empty for this record: FDA renders the date
outside both the index anchor and the first 2,000 characters of the article,
so neither extraction path fired. The events are correct; their dates are
missing.

### The magnitude is a floor, not an estimate

Three events is not a measurement of how much botanical substitution occurs
in the US market. It is a count of how many times FDA has published an
explicit substitution finding in the 67 advisories currently on the index
page. The index is not a complete historical archive, import alerts are not
yet implemented, and FDA warning letters remain outstanding. The number will
rise as coverage improves; what it already establishes is *where* to look.

`plant_part_substitution` returned zero across all three runs. Plant-part
identity is a regulatory requirement (21 CFR 101.36(b)(3); 21 USC
343(s)(2)(C)) but does not appear as explicit language in any source
implemented so far.

## 2. Kratom leads the regulatory record

| Botanical | Events | Share |
|---|---|---|
| *Mitragyna speciosa* (kratom) | 1,034 | 8.9% |
| *Cinnamomum* | 840 | 7.3% |
| *Cannabis sativa* | 808 | 7.0% |
| *Curcuma longa* (turmeric) | 763 | 6.6% |
| *Zingiber officinale* (ginger) | 565 | 4.9% |
| *Camellia sinensis* (tea) | 521 | 4.5% |
| *Allium sativum* (garlic) | 497 | 4.3% |
| *Vaccinium macrocarpon* (cranberry) | 349 | 3.0% |
| *Vaccinium corymbosum* (blueberry) | 247 | 2.2% |
| *Ginkgo biloba* | 229 | 2.0% |

Kratom's position is the notable one: it out-ranks every culinary botanical
despite having no food use, and it is driven overwhelmingly by CAERS adverse
event reports rather than recalls. Cannabis at third reflects the post-2018
hemp and CBD market. The remainder are high-volume culinary and commodity
botanicals, whose counts track trade volume as much as risk — a botanical
present in tens of thousands of products will appear in more records than a
rare one at equal per-unit risk.

**Rates are not computed** because the denominator does not exist: neither
FDA nor NIH publishes product counts per botanical, so an event count cannot
be converted into a risk-per-product figure.

## 3. Adverse event reports dominate, and carry the least evidentiary weight

| Record type | Events | Share |
|---|---|---|
| Adverse event (CAERS) | 8,140 | 70.0% |
| 60-day notice (Prop 65) | 1,889 | 16.2% |
| Recall | 1,530 | 13.2% |

Seven in ten events come from the source with the weakest evidentiary
standing. A CAERS report is a spontaneous submission with **no causality
assessment**: it records that someone attributed a symptom to a product.
Reporting rates respond to publicity, litigation and product popularity at
least as much as to harm.

Recalls — the type carrying an actual agency determination — are 13.2%.

**Any BAER aggregate not restricted by `record_type` is dominated by
self-reported data.** The column is on every row for this reason.

## 4. Co-occurrence is a weak proxy for substitution

62 events (0.54%) name both sides of a documented adulterant pair; 10 (0.09%)
involve a `documented`-class pair. Inspecting them shows the method's limit:

| Pair observed | Most likely explanation |
|---|---|
| *Crocus sativus* ← *Curcuma longa* | Saffron and turmeric both listed in a spice blend |
| *Origanum vulgare* ← *Olea europaea* | Oregano and olive both in a food product |
| *Punica granatum* ← *Vitis vinifera* | Pomegranate and grape both in a juice blend |
| *Euterpe oleracea* ← *Vitis vinifera* | Açaí and grape in a berry blend |
| *Hydrastis canadensis* ← *Berberis aristata* | Plausibly a real formulation or substitution discussion |

Most are ingredient lists, not substitution reports. The pair table encodes
genuine adulterant relationships, but **co-occurrence in a regulatory text
does not distinguish "X was passed off as Y" from "X and Y are both in this
product"** — and in a corpus where nothing states substitution explicitly
(§1), the latter dominates.

The pair-signal mechanism is retained because it narrows attention to 62
records worth reading by hand out of 11,636. It should not be reported as a
substitution count.

## 5. Taxonomic annotation is reliable, and its failures are informative

| Match type | Events | Share |
|---|---|---|
| EXACT | 10,800 | 92.8% |
| NONE | 439 | 3.8% |
| HIGHERRANK | 397 | 3.4% |
| FUZZY | 0 | 0% |

9,721 events (83.54% of attempted) reach a species-level identification —
EXACT at species rank in Plantae. The gap between 92.8% EXACT and 83.54%
identified is entirely genus-level entries in the vocabulary (`Cinnamomum`,
`Aloe`, `Berberis`), which resolve exactly but at rank GENUS and so correctly
fail the species test.

The 439 NONE results are not errors. *Arthrospira platensis* (spirulina) is a
cyanobacterium and fails against `kingdom=Plantae`; *Ganoderma* and
*Cordyceps* are fungi. Passing the kingdom hint is what makes the match
precise for plants, and the cost is that non-plant "botanicals" of commerce
fail visibly rather than matching something wrong. That is the intended
trade.

**Zero FUZZY matches** across 11,636 events, because the client sets
`strict=true`. A fuzzy match on a mangled label string would return a
confident-looking binomial for a plant never involved; suppressing them means
the identifications are conservative.

## 6. The complete California register, provably

48,328 distinct 60-day notices retrieved across 22 years in **98 windows,
every one returning under the 1,000-row cap**, mean 493 notices per window.

This matters more than the count. The register caps at 1,000 rows, ignores
`items_per_page` and `attach=page_N`, and **drops the newest rows when it
truncates** — so a capped query reads as "no recent notices", the opposite of
the truth. Bisecting until every window is under the cap makes completeness a
property of the retrieval rather than an assumption. To our knowledge no
other public tool retrieves this register completely.

## Limitations specific to this run

1. **Food and cosmetic contexts were excluded** by `--contexts supplement
   ambiguous`. The 11,636 is a filtered population; total botanical
   mentions across all contexts are higher.
2. **Only 25.2% of events (2,927) are classified `supplement`.** Prop 65 and
   recall product names are terse and carry no dosage form, so genuine
   supplement records often land in `ambiguous`. The supplement count is a
   floor by a wide margin.
3. **Vocabulary-limited.** 160 of 229 vocabulary botanicals appeared;
   botanicals outside the vocabulary are invisible. Event counts are floors.
4. **Event counts are not rates.** No public denominator of products per
   botanical exists.
5. **CAERS causality is not assessed** (§3), and CAERS supplies 70% of events.
6. **`unspecified` at 75.3%** limits what the adulteration-type breakdown can
   support.
7. **Advisory dates are frequently missing.** FDA renders dates outside the
   index anchor and often outside the article head, so the month-precision
   fallback does not always fire. Advisory events may carry a null date.

8. **A snapshot.** Sources update on different clocks; `provenance.json`
   records the retrieval time of all 698 requests.

## What would strengthen the record

**FDA import alerts and warning letters.** Advisories are implemented and
proved decisive (§1). Import alerts are the adjacent surveillance instrument
and are likely to carry further identity findings; warning letters remain
named in BOTREG's scope and unimplemented.

**A historical advisory archive.** The index page carries 67 current
advisories, not a complete history. Substitution counts are bounded by that,
not by the record.

**Add DSLD** for the label layer — declared ingredients and plant parts per
product. It would make a denominator possible for the first time, and it is
the only source that can support plant-part analysis at scale.

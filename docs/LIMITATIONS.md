# Limitations

Numbered so they can be cited individually.

1. **No full production run has been performed.** Everything in the repository
   is either code or fixture output. No BAER statistic should be quoted until
   `scripts/01_build_baer.py` has been run against live sources and the
   results verified.

2. **Detection is vocabulary-limited, so botanical involvement is a floor.**
   v0.1.0 covers 209 canonical botanicals and 558 surface forms, chosen for
   coverage of the traded market and of every species in the adulterant pair
   table. Any botanical outside it is invisible
   to BAER. This under-detects by an unmeasured amount and can never be read
   as an estimate of total botanical involvement. Extending the vocabulary
   changes the numbers, which is why every summary records the vocabulary
   version.

3. **Unfiltered, the record is dominated by products that are not
   supplements.** openFDA `food/enforcement` covers all food recalls, and
   the Prop 65 register covers all consumer products including cosmetics.
   Live runs surfaced cinnamon bagels and garlic cheddar from the former,
   and aloe gel, tea tree masks and shave foam from the latter. Every
   detection was correct and none was supplement adulteration. Any BAER
   figure not restricted by `product_context` is a statement about consumer
   products generally.

4. **The `ambiguous` bucket is large and unavoidable.** Prop 65 product names
   are terse — "Peruvian Naturals Organic Maca" — with no dosage form, so the
   genuine supplement signals often cannot be distinguished from bulk
   botanical commodities by text alone. Calling them `supplement` would
   overstate; the honest answer is `ambiguous`, and it means the `supplement`
   count is a floor by a wide margin.

5. **Unfiltered, the record is dominated by ordinary food.** openFDA's
   `food/enforcement` endpoint covers all food recalls. Culinary botanicals
   appear throughout bread, cheese, dips and prepared meals, and BOTREG
   detects them correctly. Any BAER figure not restricted by
   `product_context` is a statement about the food supply, not about
   supplement adulteration. The `supplement` classification is conservative
   and therefore a floor.

4. **A regulatory record is not an adjudicated finding.** Recalls, notices,
   warning letters and adverse event reports each carry a different
   evidentiary weight, and BAER mixes them deliberately while preserving
   `source` and `record_type` so users can restrict. Aggregating across them
   without restricting produces a number with no clear meaning.

5. **CAERS reports carry no causality assessment.** A report links a product
   and a symptom because someone submitted it. Reporting rates vary with
   publicity, litigation and product popularity, so CAERS counts measure
   reporting behaviour at least as much as they measure harm.

6. **Adulteration type is assigned from explicit language only.** Records that
   do not state the nature of the problem are `unspecified` rather than
   inferred. Note in particular that the FDA term "adulterated" (FD&C Act 402)
   is a broad legal category, *not* evidence of species substitution, and is
   deliberately excluded from the substitution patterns. The `unspecified`
   share is therefore large and should be reported, not hidden.

7. **The Prop 65 register is California-only and complaint-driven.** It
   reflects private enforcement activity, which concentrates on
   well-capitalised defendants and chemicals with established settlement
   values. It is not a random sample of products or of risk.

8. **openFDA's `openfda` enrichment block is empty for food records**, so
   normalised product and substance names are unavailable there. BOTREG reads
   the primary fields, which are free text and inconsistently formatted.

8. **GBIF annotation is name-based, not specimen-based.** A regulatory record
   names a plant in prose; BOTREG matches that string to the backbone. An
   EXACT match confirms the *name* resolves, not that the product contained
   that species. The distinction is the entire point of a botanical
   adulteration record and must not be collapsed.

10. **Synonymy is preserved but not resolved.** GBIF returns `synonym` and
   `status`; BAER records both without collapsing synonyms onto accepted
   names, since which name a regulator used is itself evidence.

11. **Warning letters are unstructured.** They are correspondence, not a
    dataset, and require text extraction whose recall is unmeasured.

12. **Coverage is US-only** and reflects US regulatory structure, in which
    supplements are regulated as food and require no pre-market approval.
    Findings do not transfer to jurisdictions with pre-market authorisation.

13. **A pair signal is co-occurrence, not causation.** BAER flags records
    naming both sides of a documented adulterant pair. A record may name both
    because it reports the substitution, because a product legitimately
    contains both, or because a warning letter discusses the pair
    generically. The signal narrows attention; it does not establish that a
    substitution occurred.

14. **Adulterant pair citations are not machine-verified.** Pairs were
    compiled from domain literature and each carries an evidence class, but
    the underlying references have not been checked against live records.
    `plausible` entries in particular are leads named in review literature,
    not confirmed market cases.

15. **Sources update on different clocks** — openFDA weekly, DSLD
    continuously, the Prop 65 register daily. A BAER build is a snapshot;
    `provenance.json` records the retrieval time of every request so a figure
    can be tied to a date.

# Sources: endpoints, quirks, and what each is good for

Verified 2026-09-09. Re-check before a large run; public agency APIs change
without notice.

## NIH Dietary Supplement Label Database (DSLD)

- API: `https://dsldapi.od.nih.gov/dsld/` (v9.4.0), guide at
  <https://dsld.od.nih.gov/api-guide>
- Licence: **CC0 1.0**
- ~200,000 labels, current and historical, on- and off-market
- Endpoints include `/v9/brand-products` and label detail by DSLD ID
- Returns large result sets; keep `size` small when exploring

**Caveat that matters:** DSLD participation is *voluntary*, not a regulatory
requirement. It is not a census of the market, and absence from DSLD says
nothing about a product's existence. NIH states plainly that labels may be
incomplete or inaccurate, since the manufacturer is responsible for the
content.

## openFDA

Base `https://api.fda.gov`, keyless access permitted. With a key: 240
requests/min and 120,000/day; without: 240/min and 1,000/day.

| Endpoint | Records (measured 2026-07) | Notes |
|---|---|---|
| `/food/enforcement.json` | ~29,224 | RES food recalls, 2004– |
| `/drug/enforcement.json` | ~17,793 | RES drug recalls |
| `/food/event.json` | — | CAERS adverse events |

Quirks handled by BOTREG:

- **Unparenthesized OR silently drops all but the last clause.** See README.
- **`skip` ceiling ~25,000 and `limit` max 1,000**, so a query matching more
  than ~26,000 records cannot be paged to completion. BOTREG raises
  `TruncationError` and the build script retries in yearly windows.
- **The `openfda` enrichment object is empty in food records**, so it cannot
  be used for normalised names.
- 404 means "no matches", not an error.
- Dates are `YYYYMMDD` strings; BOTREG normalises to ISO.

## FDA alerts and advisories

Index: <https://www.fda.gov/food/recalls-outbreaks-emergencies/alerts-advisories-safety-information>
US Government work. No API; HTML only.

**Why this source is not optional.** Builds over 246,938 records from RES
enforcement, CAERS and the Prop 65 register returned zero explicit botanical
substitution events, twice, under two vocabularies. FDA nonetheless states
substitution plainly — the January 2024 tejocote advisory reports products
labelled *Crataegus mexicana* root "tested and found to be **substituted
with** yellow oleander (*Cascabela thevetia*)".

Advisories are where FDA publishes **laboratory surveillance findings**: the
results of sampling and testing. Enforcement instruments record hazards;
advisories record what the product turned out to be. Botanical identity
failures surface here and essentially nowhere else in the public record.

**Extraction and its fragility.** This is the least durable client in BOTREG.
There is no API, so index and article parsing both depend on fda.gov's
template. Mitigations: index parsing and article parsing are separate
methods; `parse_index` **raises** if it finds no advisory links rather than
returning an empty list that would read as "no advisories exist"; and every
fetch is provenance-logged. Advisory dates are month-precision
("Updated August 2026"), normalised to the first of the month.

## FDA warning letters

Enforcement correspondence, US Government work. Unstructured prose. **Not yet
implemented** — advisories were prioritised because they carry the
substitution findings.

## California Prop 65 60-day notice register

- Search UI: <https://oag.ca.gov/prop65/60-day-notice-search>, records from 1988
- CSV export (the endpoint to use):
  `https://oag.ca.gov/prop65/60-day-notice-results-export_details.csv`
- Public, keyless

**Verified behaviour, measured 2026-09-09:**

| Parameter | Behaviour |
|---|---|
| `date_filter[min][date]`, `date_filter[max][date]` | **Work.** `MM/DD/YYYY`. |
| `field_prop65_report_year_value` | Works, but a single year exceeds the cap. |
| `items_per_page` | **Ignored.** A request for 100 returns ~1,000. |
| `attach=page_N` | **Ignored.** Every page returns the same rows. |

The last two appear in the site's own export links, which is misleading: a
first attempt to page a single year fetched 200 identical pages of 1,000 rows
before giving up.

**The cap.** At most 1,000 rows, no working pagination, and truncation drops
the **newest** rows — so a capped result reads as "no recent notices", the
opposite of the truth. `Prop65Client` bisects date windows until every window
returns under the cap and raises rather than returning a capped set.

**Column names, verified against the live export 2026-09-10:**

```
AG Number | Date | Noticing Party | Plaintiff Attorney | Alleged Violator(s) |
Chemicals | Source | Comments | Case ID | Case Name | Court Docket Number |
Civil Penalty | Attorney Fees | Other Payments | Type of Claim |
Relief Sought | Injunctive Relief
```

The **product column is called `Source`** — source of exposure. That is the
hardest mapping to guess and the costliest to get wrong: a run that missed it
parsed 5,398 real notices and reported zero botanical detections, because
`product_description` was left holding amendment boilerplate from `Comments`.
The client resolves columns by substring and prints the mapping it found, so a
future rename surfaces immediately rather than as a silent zero.

Free-text columns carry a Drupal field marker (`[field_prop65_comments]`)
which the client strips.

## GBIF backbone taxonomy

- `https://api.gbif.org/v1/species/match?name=...`
- Licence: **CC BY 4.0** — attribute GBIF when redistributing annotations
- Returns `usageKey`, `scientificName`, `rank`, `status`, `confidence`,
  `matchType`, and the classification

BOTREG passes `kingdom=Plantae` as a hint (many botanical common names collide
with animal genera) and `strict=true` (so a failed species match is reported
as a failure rather than silently downgraded to a genus). Both the flat and
nested response layouts are parsed, since GBIF has published both.

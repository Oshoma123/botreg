# Maintenance and update policy

BAER is a derived record built from live public sources. This document states
what is maintained, on what schedule, and under what terms, so that a user or
a registry curator can tell whether the resource is current.

## Update schedule

**BAER is rebuilt quarterly**, in January, April, July and October. Each
rebuild re-retrieves every source, re-screens with the current vocabulary, and
publishes as a new versioned release.

Sources update on different clocks — openFDA weekly, the CA Prop 65 register
daily, FDA advisories irregularly — so a BAER release is a snapshot. The
retrieval timestamp of every request is recorded in `provenance.json`, and the
provenance line at the head of every QA report names the retrieval date.

An out-of-cycle release is published when a source changes in a way that
affects correctness — an endpoint move, a schema change, or a discovered
parsing error. Those are recorded in the release notes.

## Versioning and persistent identifiers

Every release is archived by Zenodo and receives a DOI.

- **Concept DOI:** [10.5281/zenodo.22728764](https://doi.org/10.5281/zenodo.22728764)
  — always resolves to the latest version. Cite this for the resource.
- **Version DOI:** each release has its own, e.g. `10.5281/zenodo.22728765`
  for v2.0.2. Cite this to reproduce a specific result.

Semantic versioning: MAJOR for a change in what BAER counts or how it counts
it, MINOR for a new source or a vocabulary expansion, PATCH for corrections
and documentation. Both the vocabulary version and the adulterant-pair version
are recorded in every `stats.json`, because a count is not reproducible
without them.

Superseded versions remain permanently accessible through their version DOIs.
Nothing is withdrawn; corrections are issued as new versions with the change
stated, as in the v1.2.0 correction to the substitution finding.

## Content and scope

BAER indexes regulatory events that mention botanicals, drawn from:

- NIH Dietary Supplement Label Database (client planned)
- openFDA food enforcement, drug enforcement, CAERS adverse events
- FDA alerts and advisories
- California Proposition 65 60-day notice register
- GBIF backbone taxonomy for species annotation

Scope is the United States. Records run from 2004 (openFDA coverage) or 1988
(Prop 65) to the current release.

## Quality assurance

Each release ships a QA report with record counts, per-source event counts,
GBIF match-type breakdowns, named spot checks, and sanity assertions. The
software carries 89 automated tests run in CI on Python 3.9 and 3.12.

Every rate reports its denominator. Records that cannot be assessed —
no structure identifier, no declared name, absent from the reference set —
are reported in their own categories and never counted as failures.

## Terms

- **Software:** MIT
- **BAER dataset and derived outputs:** CC0 1.0
- **Upstream:** openFDA and FDA materials are US Government works; the Prop 65
  register is a California public record; DSLD is CC0; the GBIF backbone is
  CC BY 4.0 and **requires attribution** when the taxonomic annotations are
  redistributed.

No registration, authentication or fee is required for any part of BAER.

## Access

- Repository: <https://github.com/Oshoma123/botreg>
- Archive: <https://doi.org/10.5281/zenodo.22728764>
- Formats: CSV (events), JSON (statistics, provenance), Markdown (findings)
- Every release is fully regenerable from public sources with the commands in
  `README.md`; `provenance.json` records every request made.

## Contact and succession

Maintainer: Oshoma Erumiseli, [ORCID 0009-0004-3813-4650](https://orcid.org/0009-0004-3813-4650),
<Erumiseli.oshomag@gmail.com>.

Issues and contributions: <https://github.com/Oshoma123/botreg/issues>, see
`CONTRIBUTING.md`.

Should the maintainer become unable to continue, the Zenodo deposits persist
independently of the GitHub repository, and the MIT and CC0 terms permit any
party to fork and continue the resource without permission.

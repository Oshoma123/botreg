# Registry submission packets

Field-by-field content for the two registry applications. Both require the
resource to be live with a persistent identifier, which it now is.

Verify each registry's current form before submitting; both revise their
schemas.

---

# 1. FAIRsharing

Submit at <https://fairsharing.org> (free account). Records are curated
before publication. Register as a **Database**.

**Name**
> BAER: Botanical Adulteration Event Record

**Abbreviation**
> BAER

**Homepage**
> https://github.com/Oshoma123/botreg

**Description**
> BAER is an open dataset of United States regulatory events that mention
> botanical ingredients, derived from primary federal and state sources and
> annotated against the GBIF taxonomic backbone. It indexes food and drug
> enforcement recalls, adverse event reports, FDA alerts and advisories, and
> California Proposition 65 sixty-day notices, identifying botanical mentions
> against a curated vocabulary and classifying each event by adulteration
> type — species substitution, plant-part substitution, contamination,
> undeclared ingredient, unapproved ingredient, or mislabeling. Every event
> records its source, record type, product context, taxonomic match quality
> and the surrounding text, so that users can restrict to the evidentiary
> standard they require. BAER is produced by BOTREG, an open-source Python
> package that also provides unified programmatic access to the underlying
> sources. The v1 release covers 247,005 records from 2004 to 2026,
> yielding 11,636 events across 160 botanicals.

**Type** Database · **Subtype** Curated, derived
**Status** Ready · **Countries** United States

**Domains** Regulatory data, Food safety, Pharmacovigilance, Taxonomy,
Natural product, Adverse event
**Subjects** Food science, Toxicology, Botany, Public health, Biodiversity
**Taxonomies** Plantae; *Homo sapiens* (adverse events)
**Keywords** botanical adulteration, dietary supplements, openFDA,
Proposition 65, GBIF, species substitution, regulatory data

**Licences** MIT (software); CC0 1.0 (dataset)
**Access** Open, no registration or fee
**Data versioning** Yes — semantic versioning, Zenodo DOI per release
**PID scheme** DOI
**Curation** Manual and automated; 89 automated tests, QA report per release

**Publications / identifiers**
> Concept DOI: https://doi.org/10.5281/zenodo.22728764
> Version DOI (v2.0.2): https://doi.org/10.5281/zenodo.22728765

**Related standards** DOI; CITATION.cff; GBIF Backbone Taxonomy;
InChIKey (for chemical adulterants)

**Related databases** openFDA; NIH Dietary Supplement Label Database;
GBIF; California OEHHA Proposition 65 list

**Contact** Oshoma Erumiseli · Erumiseli.oshomag@gmail.com ·
ORCID 0009-0004-3813-4650 · Independent Researcher, Corvallis, Oregon, USA

---

# 2. re3data

Suggest at <https://www.re3data.org/suggest>. Curators assess whether the
resource is a **research data repository**.

**Be straightforward about the classification question.** BAER is a curated,
versioned dataset with DOIs, a documented update schedule and stated terms —
not an institutional deposit service. Say so in the comment field rather than
leaving a curator to work it out; a rejection on those grounds is a fair
outcome, and overstating the case would be worse than the rejection.

**Repository name**
> BAER: Botanical Adulteration Event Record

**Additional names** BOTREG/BAER
**URL** https://github.com/Oshoma123/botreg
**PID** https://doi.org/10.5281/zenodo.22728764

**Description**
> BAER is a curated, versioned dataset indexing United States regulatory
> events that mention botanical ingredients, with each botanical annotated
> against the GBIF taxonomic backbone. Sources are openFDA food and drug
> enforcement, the CAERS adverse event system, FDA alerts and advisories, and
> the California Proposition 65 sixty-day notice register. Events are
> classified by adulteration type and by product context, and every record
> carries its source, record type, taxonomic match quality and surrounding
> text so that users can restrict to a chosen evidentiary standard. The
> dataset is rebuilt quarterly, versioned semantically, and archived to
> Zenodo with a DOI per release. It is produced by BOTREG, an open-source
> Python package released alongside it, from entirely public sources; every
> release is independently regenerable and each retrieval is logged.

**Repository type** Disciplinary
**Content type** Scientific and statistical data formats; Standard office
documents; Source code
**Subject** 205 Food Science; 204 Public Health; 201 Biology (Botany);
Toxicology
**Country** United States
**Institution** Independent Researcher — Oshoma Erumiseli,
ORCID 0009-0004-3813-4650, Corvallis, Oregon, USA
**Institution type** Non-profit / independent
**Start date** 2026

**Access**
> Database access: open · Data access: open · Data upload: restricted
> (maintainer and contributors via pull request)
> No registration or fee for any access.

**Data licence** CC0 1.0 · **Software licence** MIT
**Data upload licence** Contributions accepted under the repository licences
**PID system** DOI
**Versioning** Yes — semantic; every release has a version DOI, the concept
DOI resolves to the latest
**API** No REST API for BAER itself; the BOTREG Python package provides
programmatic access to all sources and regenerates the dataset
**Metadata standards** CITATION.cff; Zenodo/DataCite metadata
**Quality management** Yes — 89 automated tests in CI, QA report per release
with stated denominators, named spot checks and sanity assertions
**Certificates** None
**Policy** https://github.com/Oshoma123/botreg/blob/main/docs/MAINTENANCE.md
**Enhanced publication** Yes — dataset, software and findings released together
**Preservation** Zenodo (CERN), indefinite

**Comment to curators**
> BAER is a curated derived dataset rather than an institutional deposit
> service, and I would rather state that plainly than have it inferred. It is
> submitted on the basis that it provides persistent, versioned, openly
> licensed access to research data with a documented update schedule, quality
> management and preservation arrangements. If re3data's scope requires a
> deposit service, a decline is a fair outcome and I would welcome the note
> so the record can be withdrawn.

**Contact** Erumiseli.oshomag@gmail.com

---

# Before submitting

1. `docs/MAINTENANCE.md` must be pushed — both packets link to it.
2. Confirm both DOIs resolve: [concept](https://doi.org/10.5281/zenodo.22728764),
   [version](https://doi.org/10.5281/zenodo.22728765).
3. Check the Zenodo record shows your ORCID and the correct author spelling.
4. FAIRsharing first — it is faster and its record can be cited in the
   re3data submission.
5. Record the outcome. Neither listing should be claimed anywhere until the
   record is published and publicly linkable.

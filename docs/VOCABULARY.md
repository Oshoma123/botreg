# The botanical vocabulary

`src/botreg/botanicals.py` holds a curated dictionary mapping canonical
scientific names to the surface forms that appear on labels and in
enforcement text. v0.1.0 covers **209 canonical botanicals / 558 surface forms**,
selected to cover (a) the commonly traded botanical supplement market and
(b) every species named in `adulterant_pairs.py`, since a pair whose species
are not in the vocabulary can never fire.

## Why a dictionary rather than inference

Treating any capitalised binomial-shaped token as a plant over-detects badly
on firm and brand names — "Nature's Bounty", "Garden of Life" — and those
false positives are invisible once aggregated. A dictionary under-detects
instead, and under-detection is measurable and can be stated as a floor.
That trade is deliberate.

## Matching rules

- Case-insensitive, with word boundaries that also exclude hyphen adjacency,
  so `aloe` does not match inside `aloeswood` and `ginger` does not match
  inside `gingerbread`.
- Internal spaces match any whitespace run, so `ma huang` matches `ma  huang`.
- **Longest surface form wins**: `siberian ginseng` resolves to
  *Eleutherococcus senticosus*, not *Panax*.
- **One hit per canonical botanical per record**, so a record naming both
  "ginkgo" and "Ginkgo biloba" counts once.

## Extending it

Add the canonical scientific name as the key and every surface form seen in
real text as values, then bump `VOCABULARY_VERSION`. Adding terms changes
every downstream count, which is why the version is recorded in each summary
and QA report — a BAER figure without its vocabulary version is not
reproducible.

Add a test alongside any addition. Negative controls matter as much as
positive ones: `test_firm_names_are_not_botanicals` and
`test_word_boundaries_prevent_substring_matches` exist because both failure
modes are easy to reintroduce.

## Genus entries

Some canonical keys are bare genera (`Teucrium`, `Aristolochia`, `Hypericum`).
That is deliberate: regulatory text frequently names only a genus
("contains germander", "Aristolochia species"), and a genus mention is real
information. GBIF will resolve these at rank GENUS, which correctly fails the
species-identification test, so they are counted honestly.

## Known gaps in v0.1.0

- Traditional Chinese Medicine multi-herb formula names are not covered;
  only constituent species are
- Ayurvedic Sanskrit synonyms are sparse beyond the most common
- Latin American and African traded botanicals are under-represented relative
  to Asian and European ones
- Homeopathic preparation names are absent
- The vocabulary is English-language; Spanish and Chinese label text is not
  matched

# Contributing to BOTREG

Contributions are welcome: vocabulary additions, new source clients, bug
reports, and BAER builds run against other date ranges.

## Reporting issues

Open an issue at <https://github.com/Oshoma123/botreg/issues>. For a parsing
or query problem, include the source, the query, and the response you got.

## Contributing code

1. Fork and branch.
2. `pip install -e ".[dev]"`.
3. Add tests. Anything touching query construction needs a test proving the
   unsafe form is rejected, not merely that the safe form works.
4. `pytest tests/ -v` must pass on Python 3.9 and 3.12.
5. Open a pull request describing what changed and why.

## Adding vocabulary

See `docs/VOCABULARY.md`. Bump `VOCABULARY_VERSION`, and add a negative
control test alongside any positive one — over-detection on brand names is
the failure mode that does not announce itself.

## Adding a source client

Subclass `BaseClient` so provenance logging and throttling are inherited, emit
`RegulatoryRecord`, normalise dates to ISO on ingest, and document the
source's quirks in `docs/SOURCES.md`. If the source can return a silently
truncated result, raise `TruncationError` rather than returning it.

## Seeking support

Open an issue with the `question` label, or contact
<Erumiseli.oshomag@gmail.com>.

## Code of conduct

Be respectful and constructive. Harassment of any kind is not tolerated.

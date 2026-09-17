# Changelog

## v1.0.3 - PostgreSQL numeric contract fix

- Fixed persistence of `ModelMatchConfidence` against PostgreSQL `numeric(5,4)`.
- Matching confidence values expressed as percentages (e.g. `100.0`) are normalized to fractions (e.g. `1.0`) at the persistence boundary.
- Applied the same defensive normalization to enrichment confidence, historical probability, and final score.
- Added validation tests for percentage/fraction inputs and invalid values.
- Existing .NET/EF Core database ownership remains unchanged.

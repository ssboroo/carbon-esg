# Factor geography and applicability policy

**Status:** Implemented on feature/factor-geography-applicability (PR #58); apply migration 0006_factor_geo_validity only after review and isolated staging validation.

## Why these fields exist

An emission factor is not fully described by a numeric value and a publication year. GHG Protocol guidance explains that emission factors can vary by region and time, and its Scope 2 guidance uses relevant grid/geographic boundaries when selecting electricity factors. The factor data/publication year is therefore not treated as proof of the dates or geography to which it applies.

## Required metadata for new factors

| Field | Meaning |
|---|---|
| geography_code | Stable uppercase code for the source's geographic boundary. |
| geography_name | Human-readable name of that boundary. |
| geography_boundary | global, national, subnational, grid, market, facility, or other. |
| valid_from / valid_to | Inclusive dates for which the source says the factor applies. |
| factor_year | Source/data publication year; kept separate from validity dates. |

The reserved code GLOBAL must use boundary global. New factor submissions require both validity dates and reject reversed intervals.

## Activity matching

Each activity record stores the actual activity geography code and name.

- A factor with geography code GLOBAL can be applied to an activity in any geography.
- Any other factor code must exactly match the activity geography code.
- The factor's inclusive validity interval must cover the entire inventory reporting period.
- A factor that fails any of these checks is rejected before activity persistence and again before a new calculation snapshot is created.

The UI pre-fills the activity geography from a non-global selected factor to reduce data-entry errors. The API remains authoritative and validates the submitted values.

## Legacy migration behavior

Rows created before this metadata existed are not assigned guessed geography or validity dates:

- geography_code = LEGACY_UNSPECIFIED;
- geography_name clearly marks the missing metadata;
- valid_from = NULL and valid_to = NULL;
- historical rows and immutable calculation snapshots are retained;
- legacy factors are excluded from new activity selection, review approval, and recalculation.

In particular, factor_year is **not** copied into valid_from/valid_to. A data year can differ from the period during which a factor is applicable.

## Scope 2 considerations

For location-based electricity factors, record the grid or other boundary actually described by the source. For market-based factors, record the relevant market/supplier boundary and retain the supporting source/contract evidence. This feature records the boundary; it does not automatically validate contractual-instrument quality criteria or decide whether market-based reporting is applicable.

## Limitations

This is a provenance and applicability control, not an emission-factor library and not a source-verification service. It does not seed factors, infer factors with AI, convert units, or claim that a selected factor is suitable merely because its metadata matches. A qualified reviewer must verify the source, denominator unit, methodology, geography, period, and version.

The current calculator still accepts CO2e-based factors. Gas-specific CO2/CH4/N2O calculations, biogenic emissions, IPCC GWP versioning, base-year recalculation, and complete GRI 102 reporting remain separate work.

## Official references

- GHG Protocol, Calculation Tools FAQ: https://ghgprotocol.org/calculation-tools-faq — factors may differ by region and time; custom values are recommended where appropriate.
- GHG Protocol, Scope 2 Guidance: https://ghgprotocol.org/scope-2-guidance — electricity factors depend on relevant geographic/grid boundaries and the selected accounting method.
- GRI, GRI 102: Climate Change 2025: https://www.globalreporting.org/publications/documents/english/gri-102-climate-change-2025/ — Scope 2 location-based and applicable market-based disclosures and factor-related requirements.
- GRI, Climate Change and Energy Topic Standards: https://www.globalreporting.org/standards/standards-development/topic-standard-for-climate-change-and-energy/ — official publication and effective-date context.

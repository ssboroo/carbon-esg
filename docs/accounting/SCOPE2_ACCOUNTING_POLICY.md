# Scope 2 accounting policy and implementation contract

**Status:** design contract for the MVP; not an assurance opinion or a claim that the platform is GHG Protocol-conformant.

## Purpose

Scope 2 covers indirect emissions from the generation of purchased or acquired electricity, steam, heat and cooling consumed by the reporting organization. The platform must keep the accounting method explicit and preserve the evidence used for every result.

This document is a prerequisite for implementing Scope 2 method selection. It deliberately adds no emission-factor values.

## Accounting methods

### Location-based

Calculate purchased energy activity using an applicable grid-average emission factor representing the electricity grid(s) on which consumption occurs. The factor must carry its geography, applicable period, energy carrier, unit, gas/CO2e basis, source, publication/version and approval evidence.

### Market-based

Use this method only where the market provides qualifying contractual instruments or supplier-specific product data. Factor provenance must identify the instrument/data class (for example, energy attribute certificate, supplier-specific rate, residual mix, or applicable grid-average proxy), the market boundary, vintage/consumption-period match, quantity covered, and evidence that the relevant quality criteria are met.

A generic grid-average factor must not be silently relabelled as a supplier-specific or contractual factor. Where residual mix or supplier-specific information is unavailable, the organization must disclose that limitation; whether a grid-average proxy is appropriate must be recorded as an explicit, reviewed methodology decision.

### Reporting

Where the applicable market has product- or supplier-choice instruments and the Scope 2 Guidance requires dual reporting, publish separate location-based and market-based totals. They are alternative views of the same purchased-energy activity and **must never be added together** into one combined Scope 2 total.

Where market-based reporting is not applicable, record the reason and report the applicable location-based result. Do not invent a market-based value.

## Required data model before implementation

Every purchased-energy activity record must carry an explicit scope_2_basis:

- location_based
- market_based

For non-Scope-2 activity records the field must be null. The API must reject a Scope 2 record with a missing basis and reject a non-Scope-2 record with a Scope 2 basis.

Every approved Scope 2 factor must declare a compatible method/basis and enough provenance to identify its source class and geography. A factor approved for one basis must not be used for the other unless a separately reviewed factor version explicitly supports that method.

The calculation snapshot must preserve, per activity line:

- scope and category;
- activity quantity and unit;
- Scope 2 basis, when applicable;
- factor identifier, immutable version, numeric value and denominator unit;
- factor source, URL/document, publication year and geographic/market boundary;
- factor source class and any contractual-instrument quality evidence;
- calculation engine and methodology version.

## Calculation and aggregation contract

1. Resolve the factor server-side from the authenticated tenant; never accept a client-supplied factor value as authoritative.
2. Validate activity/factor unit compatibility and reporting-period applicability.
3. Use deterministic decimal arithmetic and preserve the exact inputs and factor snapshot.
4. Aggregate Scope 2 into separate location_based_kgco2e and market_based_kgco2e totals.
5. Keep the overall organizational inventory total method-aware. Do not calculate Scope 1 + location-based Scope 2 + market-based Scope 2.
6. If a method is not applicable or has no eligible activity/factor data, represent it as not applicable/not available with an explicit reason; do not fabricate zero or a factor.
7. A correction creates a new activity/factor version or calculation snapshot; historical evidence is append-only.

## API and UI acceptance criteria

- Scope 2 activity entry requires a visible method selector and explains the distinction in Mongolian.
- The factor selector filters to approved factors compatible with the selected method.
- The API independently enforces the same rule; frontend validation is not a security boundary.
- The result screen shows location-based and market-based totals separately and labels the method.
- The UI warns when market-based reporting is applicable but qualifying supplier/contractual evidence is missing.
- Tests cover missing basis, wrong-basis factor, cross-tenant factor, period mismatch, duplicate/overlapping method aggregation, and the invariant that alternative Scope 2 totals are never summed.
- Historical snapshots remain reproducible after a factor is superseded.

## Standards and source notes

- GHG Protocol, Scope 2 Guidance (2015): https://ghgprotocol.org/sites/default/files/GHG%20Protocol%20Scope%202%20Guidance.pdf
- GHG Protocol, Scope 2 Guidance overview and public consultation information: https://ghgprotocol.org/scope-2-guidance
- GHG Protocol Technical Assistance, calculation method overview (updated 2026-04-07): https://ghgptechassistance.zendesk.com/hc/en-us/articles/37790958151700-How-do-I-calculate-emissions
- GRI 102: Climate Change 2025, Disclosure 102-6: https://www.globalreporting.org/publications/documents/english/gri-102-climate-change-2025/

The GHG Protocol announced a public consultation on the 2015 Scope 2 Guidance that ran from 20 October 2025 to 31 January 2026. Before shipping a production accounting rule, re-check the official Scope 2 Guidance page for any final revised standard or transition requirements. Do not treat consultation proposals as binding requirements.

## Explicit non-goals

- No default Mongolian grid or fuel factors are supplied by this document.
- No market-based claim is inferred from a green tariff label alone.
- No avoided-emissions or offset claim is netted against gross Scope 2 emissions.
- AI may assist with evidence extraction, but cannot approve a factor, choose an accounting method without user/reviewer confirmation, or calculate authoritative emissions.

## Current standards status — checked 2026-11-08

This section supersedes any older assumption that the Scope 2 revision was expected to be finalized in 2027.

- The GHG Protocol's currently published Scope 2 Guidance page still identifies the 2015 Scope 2 Guidance and records that its public consultation ran from 20 October 2025 to 31 January 2026.
- On 29 July 2026, GHG Protocol announced coordination with ISO toward one consolidated, co-branded corporate standard. The integrated public consultation is planned for Q2 2027 and the consolidated joint standard is planned for Q4 2028.
- GHG Protocol has published consultation feedback and is still exploring alternative reporting approaches for the market-based method. Those approaches are proposals under its standards-development process, not requirements to hard-code as of this review date.
- The engineering design should therefore keep method and instrument evidence versioned and configurable. It must not hard-code proposed hourly matching, deliverability, incrementality, or a future multi-statement design as if already mandatory. Reassess when the Technical Working Group and Independent Standards Board publish an approved final text.

### GRI 102: Climate Change 2025 readiness

GRI 102: Climate Change 2025 and GRI 103: Energy 2025 are published and effective for reporting from 1 January 2027. Disclosure 102-6 requires, among other things, gross location-based and, if applicable, market-based Scope 2 totals; CO2, CH4 and N2O coverage; biogenic non-CO2 emissions in gross Scope 2; separate biogenic CO2 disclosure; base-year information; consolidation approach; and methodology/factor-source disclosure. GRI's example tables show the location-based and market-based results separately, and separate gas-level detail.

The current Carbon ESG schema stores a single CO2e factor/result per activity and does not yet support all these GRI 102-6 disclosures. It must not be described as fully GRI 102: Climate Change 2025-ready until gas-specific quantities, GWP versioning, biogenic emissions, base-year/recalculation history, and comparative reporting are implemented and tested.

### Current source links

- GHG Protocol, Scope 2 Guidance (current published guidance page): https://ghgprotocol.org/scope-2-guidance
- GHG Protocol, 29 July 2026 standards-development update: https://ghgprotocol.org/blog/ghg-protocol-announces-key-standard-development-updates
- GHG Protocol, Scope 2 public consultation feedback: https://ghgprotocol.org/scope-2-public-consultation-feedback
- GRI 102: Climate Change 2025, Disclosure 102-6: https://www.globalreporting.org/publications/documents/english/gri-102-climate-change-2025/
- GRI standards development status and effective dates: https://www.globalreporting.org/standards/standards-development/topic-standard-for-climate-change-and-energy/

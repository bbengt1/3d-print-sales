# Compound + Reverse-Charge Tax Profiles

Extends `tax_profile` with two patterns from #258. Single-rate profiles continue to work unchanged.

## Compound profiles

Set `tax_profiles.is_compound = true` and add one or more `tax_profile_components` rows ordered by `apply_order` (0-indexed). Each component applies to `base + sum_of_prior_components_amounts`. Quebec-style example — GST 5% then QST 9.975% on the GST-inclusive base.

Service: `tax_service.compute_for_line(db, profile_id=..., subtotal=...)` returns a list of `TaxComputation` tuples — one per layer for a compound profile, one for a single-rate.

## Reverse-charge VAT

Set `tax_profiles.is_reverse_charge = true` (and optionally point `receivable_account_id` at a tax-receivable account). The computation propagates `is_reverse_charge=True` on each returned `TaxComputation`. Callers post **both** a payable and a receivable line of the same magnitude (net zero on the GL, but each leg surfaces separately on the tax remittance report).

## Phase 1 scope

- Schema + computation service.
- `TaxProfileComponent` CRUD via the existing `tax` admin endpoints (extending the existing UI is a follow-up; see Phase 2).
- 6 new tests covering single-rate, two- and three-layer compound, reverse-charge propagation, zero-rate, unknown profile.

## Phase 2 follow-ups

- **Wire into invoice/quote/sale tax line generation** — current callers may use `tax_profile.tax_rate` directly; switch to `compute_for_line` to handle compound + reverse-charge correctly. Audit needed.
- **Tax remittance report** breakdown by component + reverse-charge in/out.
- **Frontend** profile form: "Compound" toggle revealing the components editor; "Reverse charge" toggle revealing the receivable-account picker.

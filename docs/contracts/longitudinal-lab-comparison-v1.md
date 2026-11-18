# Longitudinal laboratory comparison v1

## Contract

`longitudinal-lab-comparison-v1`

This operation compares two final quantitative observations of one synthetic patient. Peru and Spain use the same comparison core. Each execution keeps the jurisdiction, organization, and policy of the server-selected profile.

The observations are FHIR R4 `Observation` resources already delivered by Clinical Federation. This contract does not add a second federation. A request that names both jurisdiction sources stays `cross_border_denied`.

## Dated series

The original undated seed observations stay as they are. The connector appends one dated pair and tags it `longitudinal-series`.

| Profile | Patient | Code | Prior | Recent | Difference |
| --- | --- | --- | --- | --- | --- |
| `pe-lab-demo-v1` | `PE-PAT-001` | LOINC `718-7` | 2026-10-01, 12.8 g/dL | 2026-11-15, 13.4 g/dL | +0.6 g/dL |
| `es-lab-demo-v1` | `ES-PAT-001` | LOINC `2345-7` | 2026-10-01, 95 mg/dL | 2026-11-15, 90 mg/dL | -5 mg/dL |

Both pairs use UCUM `http://unitsofmeasure.org`, status `final`, `effectiveDateTime`, and the same specimen and method within the pair. These rows are synthetic test data.

The clinical date is `effectiveDateTime` with a UTC instant. `issued` is not a substitute. `effectivePeriod`, a missing date, or a date that is not that instant form is denied. The denied comparison is not given another date.

## Comparison

Before any model call, both observations must have the same verified patient, the same authorized organization and jurisdiction, the same code and coding system, a numeric quantity, the same UCUM code, ordered clinical dates, status `final`, and the same specimen and method. A missing or different specimen or method is not comparable. Two observations with the same code and unit are not comparable for that reason alone.

The engine uses decimal arithmetic. It records the prior value, the recent value, both dates, the signed difference, and the direction `aumento`, `disminucion`, or `sin cambio`. A percent is recorded only when the prior value is not zero. A zero prior value is `zero_baseline`. There is no unit conversion and no classification of the change as better, worse, normal, or pathological.

## Model and permit

The operation id is `longitudinal-lab-comparison-v1`. The policies are `pe-longitudinal-lab-policy-v1` and `es-longitudinal-lab-policy-v1`. The authorization ids are `pe-longitudinal-001` and `es-longitudinal-001`. Ledger schema 9 accepts those pairs. Schema 8 does not.

The permit is not a permit for `jurisdiction-lab-summary-v1`, `external-fhir-lab-summary-v1`, `lab-result-summary-v1`, or `vacation-days-v1`. The gateway allows one intercepted Gemini call, one reservation, and no automatic retry. `request_real_provider_send()` stays closed.

The model receives the code, the verified values and unit, the clinical dates, the calculated difference, the observation ids, and the source. It does not receive a personal name. The stored comparison is copied from the resources and the engine. A model sentence that changes a value, a date, a unit, the difference, or a reference is rejected.

## Review

A new review can store one longitudinal evidence row. The dashboard shows that row when it exists: prior result, recent result, calculated change, both dates, both sources, the generated text, and the review state. A human decision does not rewrite the summary or the evidence. Historical reviews stay readable when the table is absent.

This is not a diagnosis, a production alert, or a RENHICE, HCDSNS, or EHDS conformance claim.

# MINI_HIS_TERMINOLOGY_V1

## Status

Laboratory contract for two static maps inside `services/fhir-integration-service`. Both are source. Neither is a terminology server, a FHIR ValueSet, or a FHIR ConceptMap. This document does not record a test execution.

The maps apply only when Clinical Read normalizes Mini HIS JSON. They do not apply to Epic, Oracle, or resources read from HAPI.

Package: `lab.healthcare.fhir.terminology`. Integration id: `mini-his`.

## Registries

| Registry | Map-set version | Responsibility |
|---|---|---|
| `StaticTerminologyRegistry` | `mini-his-maps-v1` | Encounter status, encounter class, observation status, observation category, and appointment status. |
| `StaticQuantityUnitRegistry` | `mini-his-ucum-v1` | Quantity unit text, UCUM system, and UCUM code. |

The versions name these laboratory map sets. `mini-his-maps-v1` is not a LOINC, SNOMED, or UCUM release. `mini-his-ucum-v1` is not a UCUM specification version. The two registries do not share a domain enum. Units are not values of `TerminologyDomain`.

## Status, class, and category

`TerminologyRegistry.resolve` throws `TerminologyMappingNotFound` when the integration, domain, or source code is unknown or blank. `MiniHisNormalizer` turns that into Clinical Read HTTP 422 `invalid_source`. There is no silent fallback and no invented code.

| Domain | Source | FHIR code | System |
|---|---|---|---|
| `ENCOUNTER_STATUS` | `completed` | `finished` | none |
| `ENCOUNTER_STATUS` | `in_progress` | `in-progress` | none |
| `ENCOUNTER_CLASS` | `ambulatory` | `AMB` | `http://terminology.hl7.org/CodeSystem/v3-ActCode` |
| `OBSERVATION_STATUS` | `final` | `final` | none |
| `OBSERVATION_CATEGORY` | `laboratory` | `laboratory` | `http://terminology.hl7.org/CodeSystem/observation-category` |
| `OBSERVATION_CATEGORY` | `vital_sign` | `vital-signs` | `http://terminology.hl7.org/CodeSystem/observation-category` |
| `APPOINTMENT_STATUS` | `not_attended` | `noshow` | none |
| `APPOINTMENT_STATUS` | `confirmed` | `booked` | none |

Encounter class display stays the source word `ambulatory`. A status mapping that carries a target system, or a class or category mapping whose system does not match the constant above, is `invalid_source`.

Appointment `participant.status` is always `needs-action`. That value is not one of these mappings. The simulator does not record an individual response, and appointment status is not copied onto the participant.

Observation `code` is the proprietary display text. This map does not assign LOINC or SNOMED.

## UCUM quantities

`QuantityUnitRegistry.find` returns an empty result for an unknown, blank, or other-integration unit. It does not throw and it does not guess. Matching is exact and case-sensitive.

System for a known unit: `http://unitsofmeasure.org`.

| Source unit | `Quantity.unit` | `Quantity.code` |
|---|---|---|
| `g/dL` | `g/dL` | `g/dL` |
| `mmHg` | `mmHg` | `mm[Hg]` |

`MiniHisNormalizer.applyQuantity` writes the original decimal as `Quantity.value`. It does not convert numbers and it does not interpret a clinical string such as `120/80`.

It applies to `Observation.valueQuantity` and to `Observation.component.valueQuantity`:

- A known unit sets `unit`, `system`, and `code`.
- An unknown unit sets `unit` to the source text and omits `system` and `code`.
- A null unit on a decimal value sets `value` only.
- A non-decimal value with no unit stays `valueString`.
- A non-decimal value with a unit is `invalid_source`.
- A component requires a unit and a decimal. A missing or blank component unit remains `invalid_source`.

Blood-pressure components stay structured quantities. The parent value text is not parsed into those components.

## Limitations

- There is no terminology server and no `$validate-code`, `$expand`, or `$translate` on these maps.
- UCUM is not validated beyond the two rows. `MMHG`, `mg/dL`, and any other token stay uncoded.
- There is no general LOINC or SNOMED coding.
- Numeric clinical values are copied, not converted.
- Coverage is the Mini HIS normalizer only.

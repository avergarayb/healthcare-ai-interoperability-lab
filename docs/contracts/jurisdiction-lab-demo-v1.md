# Jurisdiction laboratory demonstration v1

## Contract

`jurisdiction-lab-demo-v1`

One process loads one profile from `JURISDICTION_LAB_ENABLED` and `JURISDICTION_LAB_PROFILE`. The default is disabled. The checked-in federation grant does not include a jurisdiction source until that process enables it.

## Profiles

| Profile | Jurisdiction | Organization | Policy | Patient value | Guide cited |
| --- | --- | --- | --- | --- | --- |
| `pe-lab-demo-v1` | PE | `org-pe-lab-demo` | `pe-lab-demo-policy-v1` | `PE-PAT-001` | CorePE 0.1 draft, FHIR R4 4.0.1 |
| `es-lab-demo-v1` | ES | `org-es-lab-demo` | `es-lab-demo-policy-v1` | `ES-PAT-001` | HL7 Europe Base 2.0.0, informative; IPS 2.0.1 informative |

Both use LOINC `http://loinc.org` and UCUM `http://unitsofmeasure.org`. The operation id is `jurisdiction-lab-summary-v1`. Authorization ids are `pe-lab-demo-001` and `es-lab-demo-001`.

CorePE 0.1 was published as a draft on 2026-06-19. Its package version is not valid semver. HL7 Europe Base and Core 2.0.0, published as STU 2 on 2026-04-27, is superseded by 2.0.1. Neither citation is a national certification. A laboratory observation set is not an IPS document.

## Validation classes

- `fhir-r4-checked`: the resource has the structural fields this laboratory checks.
- `internal-demo-rules`: the resource matches the closed synthetic profile.
- Official profile validation: not performed.
- `profile_not_verified`: the resource claims an official canonical or lacks the demonstration tags.
- A failed check does not become a clinical conclusion.

## Boundary

Patients, organizations, permits, reviews, and evidence stay in the selected jurisdiction. There is no clinical transfer between Peru and Spain. Synthetic resources do not carry names, birth dates, addresses, or national identifiers. Absence of those fields is not anonymization.

The model receives the minimized chart for the server-selected profile. Cited evidence stored for a new review is copied from that chart: source, resource id, code, value, UCUM system and code, status, provenance reference, profile id, and validation version. It is not parsed from the generated text. The summary row remains pending until a human decision, and that decision does not rewrite it.

The same connector may also return dated observations tagged `longitudinal-series`. The summary minimizer ignores that tag and still requires the original undated seed. Those dated observations belong to [longitudinal-lab-comparison-v1](longitudinal-lab-comparison-v1.md). They do not change this summary contract.

Later regulatory work, not this contract, includes GDPR roles and rights, ENS controls, EHDS obligations, and RENHICE operational integration.

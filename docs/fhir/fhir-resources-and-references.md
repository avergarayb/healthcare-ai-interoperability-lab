# FHIR Resources and References

This note teaches how clinical facts sit **next to** a Patient, not inside it. Read it after [fhir-search.md](fhir-search.md).

The Java service is still a FHIR **client**. There is still no public REST controller and no DTO layer.

## A graph of independent Resources

FHIR does not nest Observation or Condition inside Patient JSON. Each is its own Resource. They are linked with a **Reference**.

```text
                    Patient/patient-001
                    /               \
                   /                 \
                  v                   v
      Observation/obs-001      Condition/condition-001
             |                         |
             | subject                 | subject
             +------------+------------+
                          v
                   Patient/patient-001
```

| Resource | Clinical meaning |
|---|---|
| `Patient` | Who the person is (demographics, identifiers). |
| `Observation` | A measurement or assertion: a vital sign, lab result, or finding at a point in time. |
| `Condition` | A problem or diagnosis that is (or was) true of the patient. |

`Observation` is "we measured / observed this". `Condition` is "this patient has this problem". A blood-pressure reading is an Observation. Hypertension as a diagnosis is a Condition. They can describe the same person without being the same resource.

## Logical ID, identifier, and Reference

These three strings look similar and are not interchangeable.

| Concept | Example | Used in |
|---|---|---|
| Logical ID | `patient-001` | `GET /Patient/patient-001` |
| Business identifier | `MRN-10001` | `GET /Patient?identifier=MRN-10001` |
| Reference | `Patient/patient-001` | `Observation.subject.reference` |

A Reference is `{ResourceType}/{logicalId}` on this server. It is not the MRN.

```json
"subject": {
  "reference": "Patient/patient-001"
}
```

In Java that is `org.hl7.fhir.r4.model.Reference`. `getReference()` returns the string `Patient/patient-001`.

## Coding, CodeSystem, CodeableConcept

Clinical meaning is not a free-text label alone. FHIR uses coded terminology.

### Coding

One coded concept:

```text
system  = http://loinc.org
code    = 85354-9
display = Blood pressure panel
```

`code` only means something **inside** `system`. `85354-9` without LOINC is ambiguous.

### CodeSystem

`http://loinc.org` identifies **LOINC** (laboratory and clinical observations).

`http://snomed.info/sct` identifies **SNOMED CT** (clinical findings, disorders, procedures).

The URI is the CodeSystem. The `code` is the concept in that system.

### CodeableConcept

```text
CodeableConcept
    └── coding[]
          └── Coding
```

One clinical idea can carry several Codings (LOINC and SNOMED at once). This lab stores a single Coding per resource. We do not translate between systems.

## Observation/obs-001

A simplified blood-pressure-related Observation for Maria Garcia.

R4 requires `status` and `code`. We also set `subject` (the Reference) and a single quantity `130 mmHg`.

A real blood-pressure **panel** (LOINC `85354-9`) normally has systolic and diastolic **components**. This example uses one quantity on purpose: the lesson is Resource + Reference + Coding, not vital-sign modeling.

### FHIR HTTP

```http
GET /Observation/obs-001
```

Result: an `Observation` resource, not a Bundle.

### HAPI FHIR Java

```java
fhirClient
    .read()
    .resource(Observation.class)
    .withId("obs-001")
    .execute();
```

Java mapping:

```text
Observation
 ├── status
 ├── code
 │    └── CodeableConcept
 │         └── Coding          (LOINC 85354-9)
 ├── subject
 │    └── Reference            (Patient/patient-001)
 └── valueQuantity             (130 mmHg, UCUM mm[Hg])
```

## Condition/condition-001

Hypertensive disorder (SNOMED CT `38341003`) for the same patient.

R4 requires `subject`. We also set `code` and `clinicalStatus=active` so the Condition is a complete, realistic problem-list entry.

### FHIR HTTP

```http
GET /Condition/condition-001
```

### HAPI FHIR Java

```java
fhirClient
    .read()
    .resource(Condition.class)
    .withId("condition-001")
    .execute();
```

## Search by patient

The resource element is `subject`. The **search parameter** is `patient`. They are related but not the same name.

```http
GET /Observation?patient=patient-001
GET /Condition?patient=patient-001
```

HAPI:

```java
fhirClient.search()
    .forResource(Observation.class)
    .where(Observation.PATIENT.hasId("patient-001"))
    .returnBundle(Bundle.class)
    .execute();

fhirClient.search()
    .forResource(Condition.class)
    .where(Condition.PATIENT.hasId("patient-001"))
    .returnBundle(Bundle.class)
    .execute();
```

`Observation.PATIENT` / `Condition.PATIENT` are HAPI's typed form of the FHIR search parameter `patient`.

Search still returns a **Bundle** (`searchset`). Read still returns the resource.

```text
Bundle
 └── entry[]
      └── resource
           └── Observation or Condition
```

This lab does **not** use `_include` or `_revinclude` in the basic Patient/Observation/Condition searches. Those parameters are documented in [fhir-include-revinclude.md](fhir-include-revinclude.md).

## Follow the Reference

After reading Observation or Condition:

```java
fhirService.subjectReference(observation.getSubject());
// "Patient/patient-001"
```

Then, if you need the Patient body:

```http
GET /Patient/patient-001
```

That is two REST calls. FHIR does not automatically embed the Patient.

## Load synthetic data

The same script as Patient search now PUTs every `scripts/fhir/*.json`, **Patients first** so references resolve:

```powershell
pwsh -File scripts/fhir/load-synthetic-patients.ps1
```

```http
PUT /Patient/patient-001
PUT /Observation/obs-001
PUT /Condition/condition-001
```

Integration tests seed the same resources with HAPI `update()` before they run.

All data is synthetic.

## Tests

```bash
cd services/fhir-integration-service
mvn test
mvn verify -Pintegration
```

Unit tests mock `IGenericClient`. Integration tests need local HAPI.

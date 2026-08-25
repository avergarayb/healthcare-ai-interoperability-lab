# FHIR terminology and `$validate-code`

This note teaches how FHIR represents **coded clinical meaning** and how `$validate-code` checks a code against a terminology context. Read it after [fhir-resources-and-references.md](fhir-resources-and-references.md).

The Java service remains a FHIR **client**. There is no custom terminology server, no external LOINC/SNOMED service, and no DTO.

## Terminology model

```text
CodeSystem
    ↓
defines concepts/codes and their meanings

ValueSet
    ↓
selects which codes are allowed for a context

Coding
    ↓
one coded representation (system + code + display)

CodeableConcept
    ↓
a clinical idea represented by one or more Codings
```

### CodeSystem

A CodeSystem is the **definition** of a terminology: which codes exist and what they mean. It is more than a list. It is the identity and semantics of a code family.

Examples used in this lab:

```text
http://loinc.org          LOINC (observations, labs, panels)
http://snomed.info/sct    SNOMED CT (findings, disorders, procedures)
```

Local HAPI starts with **no** CodeSystem resources (`GET /CodeSystem` total = 0). It does not ship a full LOINC or SNOMED dictionary.

### ValueSet

A ValueSet is a **selection** of codes for a use (for example “codes allowed on Observation.code in this profile”).

```text
CodeSystem → defines the universe of concepts
ValueSet   → picks the subset allowed in a context
```

Validation can target a CodeSystem (`url` of the system) or a ValueSet. This local HAPI also has **no** ValueSet resources (`GET /ValueSet` total = 0). This lab does **not** invent an external ValueSet URL.

### Coding

One coded concept:

```json
{
  "system": "http://loinc.org",
  "code": "85354-9",
  "display": "Blood pressure panel"
}
```

| Field | Role |
|---|---|
| `system` | which CodeSystem |
| `code` | the concept **inside** that system |
| `display` | human-readable text (not the identity) |

The identity is **`system` + `code`**. `85354-9` without LOINC is ambiguous.

### CodeableConcept

```text
CodeableConcept
    └── coding[]
          ├── Coding #1  (e.g. LOINC)
          └── Coding #2  (e.g. SNOMED CT)
```

One clinical idea may be written in more than one terminology. Multiple Codings are **not** automatically equivalent. Equivalence needs a ConceptMap / terminology knowledge. This lab does not implement `$translate`.

## Existing synthetic resources

```http
GET /Observation/obs-001
```

```json
"code": {
  "coding": [
    {
      "system": "http://loinc.org",
      "code": "85354-9",
      "display": "Blood pressure panel"
    }
  ]
}
```

```http
GET /Condition/condition-001
```

```json
"code": {
  "coding": [
    {
      "system": "http://snomed.info/sct",
      "code": "38341003",
      "display": "Hypertensive disorder"
    }
  ]
}
```

In Java:

```java
CodeableConcept concept = observation.getCode();
Coding coding = concept.getCodingFirstRep();
coding.getSystem();
coding.getCode();
coding.getDisplay();
```

`FhirService.primaryCoding(concept)` reads that first Coding. It is not a DTO.

## Search versus `$validate-code`

```http
GET /Observation?code=85354-9
```

asks: *which Resources contain this coded concept?* Result: `Bundle` with `Observation/obs-001`.

```http
GET /CodeSystem/$validate-code?url=http://loinc.org&code=85354-9
```

asks: *is this code valid in that CodeSystem / context?* Result: `Parameters`, not a list of Observations.

Search does **not** prove the code is a real LOINC term. It only finds resources that stored that string.

## `$validate-code`

`$validate-code` is a FHIR **operation**. It is terminology validation, not “the patient has this diagnosis.”

### Parameters vs Bundle

```text
Bundle      → groups Resources (search, transaction)
Parameters  → named operation inputs/outputs
```

Typical output:

```json
{
  "resourceType": "Parameters",
  "parameter": [
    { "name": "result", "valueBoolean": false },
    { "name": "message", "valueString": "CodeSystem is unknown..." }
  ]
}
```

`result` is the validation boolean. HTTP 200 only means the **operation ran**. It does not mean the code is valid.

### OperationOutcome

`OperationOutcome` carries errors, warnings, and informational details. A 400 from a malformed `$validate-code` (missing `url`) returns OperationOutcome. A successful call with `result=false` usually returns **Parameters**, not a 4xx. Do not treat every OperationOutcome as a transport failure, and do not treat HTTP 200 as “valid code.”

## Local HAPI behavior (observed)

Working GET (CodeSystem identifier required):

```http
GET /CodeSystem/$validate-code?url=http://loinc.org&code=85354-9
```

| Input | HTTP | `result` | Message (concise) |
|---|---|---|---|
| LOINC `85354-9` | 200 | **false** | CodeSystem unknown: `http://loinc.org` |
| LOINC `99999999` | 200 | **false** | CodeSystem unknown: `http://loinc.org` |
| SNOMED `38341003` | 200 | **false** | Terminology service unable to validate |
| SNOMED `99999999` | 200 | **false** | Terminology service unable to validate |

This server has **no** LOINC or SNOMED CodeSystem loaded. It cannot confirm that `85354-9` is a real LOINC code. This lab does **not** fake a successful LOINC/SNOMED validation and does **not** attach an external terminology service.

`GET /CodeSystem/$validate-code?system=...&code=...` (without `url`) returns **400** HAPI-0908: CodeSystem ID or identifier required.

`GET /ValueSet/$validate-code?url=http://hl7.org/fhir/ValueSet/observation-codes&...` returns `result=false` (cannot expand; CodeSystem not found). That URL was a probe, not a ValueSet we created.

### Synthetic lab CodeSystem (valid vs invalid)

To show a true `result=true` vs `result=false` **on this server**, tests PUT a small lab CodeSystem (same idea as synthetic Patients, not a terminology product):

```text
url  = https://example.org/lab/observation-codes
code = lab-bp-panel
```

Then:

| Code | `result` |
|---|---|
| `lab-bp-panel` | true |
| `99999999` | false |

This is **not** LOINC. It only proves HAPI can validate against a CodeSystem resource it actually stores.

## HAPI FHIR Java (8.10.0)

```java
fhirClient.operation()
        .onType(CodeSystem.class)
        .named("$validate-code")
        .withParameter(Parameters.class, "url", new UriType(system))
        .andParameter("code", new CodeType(code))
        .useHttpGet()
        .execute();
```

`FhirService.validateCode(system, code)` returns `Parameters`. `validationResult` / `validationMessage` read `result` and `message`. They do not collapse the operation to a boolean-only API at the HTTP layer.

## Out of scope

No `$expand`, `$lookup`, `$translate`, ConceptMap, UMLS, BioPortal, or vendor terminology feeds.

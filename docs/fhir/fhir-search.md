# FHIR Read and Search

This note teaches the first resource operations in `fhir-integration-service`: **read** and **search**. Read it together with [fhir-client.md](fhir-client.md).

The Java service is still a FHIR **client**. HAPI FHIR in Docker is still the **server**. No public REST controller was added.

## Why deterministic synthetic data

Search tests are useless if the server contains unknown Patients. We load three fixed, fake people so that:

- `GET /Patient/patient-001` always returns Maria Garcia;
- `GET /Patient?name=Maria` always returns two people;
- `GET /Patient?identifier=MRN-10001` always returns one person.

All data is synthetic. There is no real PHI.

## Logical ID vs identifier

These are not the same thing.

| Concept | Example | How you query it |
|---|---|---|
| **Logical ID** | `patient-001` | Path: `/Patient/patient-001` |
| **Identifier** | `MRN-10001` | Search: `/Patient?identifier=MRN-10001` |

The logical ID is the resource's technical id on **this** server. The identifier is a business/clinical identifier (here a fake MRN).

```http
GET /Patient/patient-001
```

returns that one resource, or 404. It does **not** look at `Patient.identifier`.

```http
GET /Patient?identifier=MRN-10001
```

asks the server: "which Patient resources have this identifier?" The answer is a **Bundle**, even if only one matches.

Juan Garcia shows the split clearly:

- logical ID `patient-002`
- identifier `MRN-10002`

`GET /Patient/MRN-10002` is the wrong question. That would look for a resource whose **id** is the string `MRN-10002`.

## Read — one Patient, not a Bundle

### FHIR HTTP

```http
GET /Patient/patient-001
```

Expected body: a `Patient` resource.

### HAPI FHIR Java

```java
fhirClient
    .read()
    .resource(Patient.class)
    .withId("patient-001")
    .execute();
```

| Piece | Meaning |
|---|---|
| `read()` | FHIR read interaction |
| `resource(Patient.class)` | resource type `Patient` |
| `withId("patient-001")` | logical ID in the URL path |
| `execute()` | send `GET /Patient/patient-001` |

`FhirService.readPatient("patient-001")` wraps that call. If the server has no such id, HAPI throws `ResourceNotFoundException`. We wrap it in `FhirClientException` and do **not** return null.

## Search — a Bundle of matches

Search never returns a bare `Patient`. It returns a `Bundle` of type `searchset`.

```text
Bundle
 └── type: searchset
 └── total
 └── entry[]
      └── resource
           └── Patient
```

`FhirService.extractPatients(bundle)` walks `entry[]` and collects the `Patient` resources. It is not a generic Bundle framework.

### Search parameter `name`

`name` is a **FHIR search parameter** defined for Patient. It is not a random Java argument. It typically matches given or family name.

```http
GET /Patient?name=Maria
```

HAPI equivalent:

```java
fhirClient
    .search()
    .forResource(Patient.class)
    .where(Patient.NAME.matches().value("Maria"))
    .returnBundle(Bundle.class)
    .execute();
```

| Piece | Meaning |
|---|---|
| `search()` | FHIR search interaction |
| `forResource(Patient.class)` | `/Patient` |
| `Patient.NAME` | search parameter `name` |
| `matches().value("Maria")` | `?name=Maria` |
| `returnBundle(Bundle.class)` | parse the searchset |

With the synthetic dataset this returns **Maria Garcia** (`patient-001`) and **Maria Lopez** (`patient-003`). It does **not** return Juan Garcia.

Do not assume entry order. Collect IDs into a set before asserting.

### Search parameter `identifier`

`identifier` is a token search parameter against `Patient.identifier`.

```http
GET /Patient?identifier=MRN-10001
```

HAPI equivalent:

```java
fhirClient
    .search()
    .forResource(Patient.class)
    .where(Patient.IDENTIFIER.exactly().identifier("MRN-10001"))
    .returnBundle(Bundle.class)
    .execute();
```

Expected: a Bundle with one Patient, logical ID `patient-001`.

That is how you look up an MRN. It is not `GET /Patient/MRN-10001`.

## Why the service returns FHIR types

`FhirService` returns `Patient` and `Bundle`, not a lab DTO.

At this stage the lesson is the FHIR wire model. A DTO would hide `Bundle.entry` and the ID vs identifier distinction. A normalized healthcare model comes later, when we have a reason to decouple callers from FHIR.

## Error handling

Same strategy as the metadata client:

- connection failures → `FhirClientException` caused by `FhirClientConnectionException`
- HTTP/FHIR errors (including 404 on read) → `FhirClientException` caused by `BaseServerResponseException`

No silent nulls.

## Load the synthetic patients

Integration tests seed the three Patients with `PUT` before they run.

To load them by hand (HAPI must be up):

```powershell
pwsh -File scripts/fhir/load-synthetic-patients.ps1
```

Equivalent HTTP:

```http
PUT http://localhost:8080/fhir/Patient/patient-001
PUT http://localhost:8080/fhir/Patient/patient-002
PUT http://localhost:8080/fhir/Patient/patient-003
```

`PUT` (not `POST`) keeps the logical IDs stable.

## Verify against the server

```http
GET http://localhost:8080/fhir/Patient/patient-001
GET http://localhost:8080/fhir/Patient?name=Maria
GET http://localhost:8080/fhir/Patient?identifier=MRN-10001
```

## Tests

Unit tests (`mvn test`) mock `IGenericClient`. They do not need Docker.

Integration tests need local HAPI:

```bash
cd services/fhir-integration-service
mvn verify -Pintegration
```

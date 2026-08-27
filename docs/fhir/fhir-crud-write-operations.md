# FHIR CRUD and write operations

This note teaches FHIR **create, read, update, and delete** against local HAPI FHIR. Read it after [fhir-include-revinclude.md](fhir-include-revinclude.md).

The Java service is still a FHIR **client**. There is no REST controller, no DTO, and no local copy of FHIR resources in application tables.

## Resource lifecycle, not SQL CRUD

```text
CREATE → READ → UPDATE → DELETE
```

These are FHIR *interactions* on a Resource identity. They are not a Spring repository and not a SQL `INSERT`/`UPDATE`/`DELETE` on a table we own. HAPI FHIR remains the server of record.

```text
POST /Patient
       ↓
server assigns logical ID
       ↓
GET /Patient/{id}
       ↓
PUT /Patient/{id}
       ↓
GET /Patient/{id}
       ↓
DELETE /Patient/{id}
       ↓
GET /Patient/{id}
       ↓
404 Not Found  or  410 Gone
```

## Operation map

| Operation | HTTP | HAPI FHIR | Result |
|---|---|---|---|
| Create | `POST /Patient` | `client.create().resource(patient).execute()` | `MethodOutcome` with created identity |
| Read | `GET /Patient/{id}` | `client.read().resource(Patient.class).withId(id).execute()` | `Patient` |
| Update | `PUT /Patient/{id}` | `client.update().resource(patient).execute()` | `MethodOutcome` with that identity |
| Delete | `DELETE /Patient/{id}` | `client.delete().resourceById("Patient", id).execute()` | `MethodOutcome` |

## POST versus PUT

This distinction is the main learning objective.

```http
POST /Patient
```

Meaning: *create a new Patient and let the server assign its logical ID*.

The URL does **not** contain an id. Even if the JSON body has an `id` field, HAPI's create interaction is still a POST to the type endpoint. The server chooses the identity. Do not assume it will be `patient-004` or any other guessed value.

```http
PUT /Patient/patient-write-001
```

Meaning: *write this Patient at the logical ID `patient-write-001`*.

If that id does not exist and the server allows it, PUT can create the resource at the client-chosen id. If it already exists, PUT replaces the representation.

| | POST | PUT |
|---|---|---|
| URL | `/Patient` | `/Patient/{id}` |
| Who chooses the logical ID | server | client (from the resource id / path) |
| Typical create status | `201 Created` | `201 Created` when the id was new |
| Typical update status | not used | `200 OK` |
| Lab method | `createPatient` | `updatePatient` |

The existing seed data (`patient-001`, `obs-001`, `condition-001`) already used PUT with client-assigned ids. This task also shows POST, where the id is unknown until `MethodOutcome` returns.

## MethodOutcome

HAPI write calls do not return a `Patient` the way `read()` does. They return `MethodOutcome`.

```java
MethodOutcome outcome = fhirClient.create()
        .resource(patient)
        .execute();

String logicalId = outcome.getId().getIdPart();
Boolean created = outcome.getCreated();
```

| Piece | Meaning |
|---|---|
| `getId()` | identity from the `Location` header (`Patient/{id}/_history/{vid}`) |
| `getIdPart()` | the logical ID only (`42`, `patient-write-001`, …) |
| `getCreated()` | `true` when the server reported HTTP `201` |
| `getResource()` | often **null** unless the client asked for `Prefer: return=representation` |

This lab does **not** send `Prefer`. After create, the next step is a real read:

```text
create()  →  MethodOutcome.id
                 ↓
              read()
                 ↓
              Patient
```

That round trip is an important integration test: it proves the server persisted the resource, not only that HAPI built a client-side object.

`FhirService.createdLogicalId(outcome)` reads the id part and fails if the outcome has no identity. Tests must capture that value. They must not hardcode the generated id.

## HTTP status semantics

| Status | Typical cause |
|---|---|
| `201 Created` | POST create, or PUT at a new logical ID |
| `200 OK` | PUT update of an existing id, or GET of an existing resource |
| `204 No Content` | some servers on DELETE (HAPI may still return a body / OperationOutcome) |
| `404 Not Found` | GET of an id that never existed |
| `410 Gone` | GET of an id that existed and was then deleted, when the server keeps history |

HAPI JPA keeps version history by default. After `DELETE /Patient/{id}`, a later `GET /Patient/{id}` is often **410 Gone**, not 404. Both mean "this identity is not available for normal retrieval". `FhirService` still wraps the HAPI exception in `FhirClientException`. It does **not** turn that into `null`.

## Create — POST /Patient

Synthetic Patient used for POST (no client `id`):

```text
Name: Ana Torres
Gender: female
Birth date: 1992-06-10
Identifier: MRN-10004
```

### FHIR HTTP

```http
POST /Patient
Content-Type: application/fhir+json
```

### HAPI FHIR Java

```java
fhirClient.create()
        .resource(patient)
        .execute();
```

`FhirService.createPatient(patient)` wraps that call.

## Read — GET /Patient/{id}

Unchanged from [fhir-search.md](fhir-search.md). After create, the `{id}` is the value from `MethodOutcome`, not a name we invented.

```http
GET /Patient/{generated-id}
```

```java
fhirClient.read()
        .resource(Patient.class)
        .withId(generatedId)
        .execute();
```

## Update — PUT /Patient/{id}

Change a field on the resource you just read, keep the same logical ID, and PUT the whole representation.

Example:

```text
family: Torres  →  Torres-Gomez
```

### FHIR HTTP

```http
PUT /Patient/{generated-id}
Content-Type: application/fhir+json
```

### HAPI FHIR Java

```java
patient.setId(generatedId); // already present after read
fhirClient.update()
        .resource(patient)
        .execute();
```

The logical ID on the resource selects the URL. That is the opposite of POST.

PUT **replaces** the resource at that id. It is not a partial edit.

## PUT with a client-assigned ID

```http
PUT /Patient/patient-write-001
```

Synthetic Patient:

```text
Patient/patient-write-001
Name: Carlos Mendoza
Identifier: MRN-10005
```

The Java object carries `id = patient-write-001`. HAPI then sends PUT to that path. Afterwards `GET /Patient/patient-write-001` returns Carlos Mendoza.

This is how the lab already seeded `patient-001`. POST is the other way: the client does not choose the id.

## Delete — DELETE /Patient/{id}

```http
DELETE /Patient/{generated-id}
```

```java
fhirClient.delete()
        .resourceById("Patient", generatedId)
        .execute();
```

Normal retrieval then fails (`404` or `410`). This task does not inspect `_history` or resource versions.

## Observation create and references

Writes can carry `Reference` values. A new Observation created with POST still points at the existing synthetic Patient:

```http
POST /Observation
```

Required R4 elements used here:

| Element | Why |
|---|---|
| `status` | mandatory (`1..1`) |
| `code` | mandatory (`1..1`); LOINC `85354-9` |
| `subject` | not required by the base spec, required for this lab so the Observation joins `Patient/patient-001` |

```json
{
  "resourceType": "Observation",
  "status": "final",
  "code": {
    "coding": [
      {
        "system": "http://loinc.org",
        "code": "85354-9",
        "display": "Blood pressure panel"
      }
    ]
  },
  "subject": {
    "reference": "Patient/patient-001"
  }
}
```

```java
fhirClient.create()
        .resource(observation)
        .execute();
```

After create, read the generated id and check:

- `subject.reference` is still `Patient/patient-001`
- the LOINC code is still `85354-9`

The server-assigned Observation id will not be `obs-001`. That id remains the seeded resource from the previous task.

## PUT versus PATCH

```http
PUT /Patient/{id}
```

replaces the representation at that logical ID.

```http
PATCH /Patient/{id}
```

would change selected elements. This lab does **not** implement PATCH.

## Conditional operations are out of scope

Not implemented:

```http
POST /Patient?identifier=https://example.org/lab/mrn|MRN-10004
```

That is *conditional create*: create only if no match exists. Also out of scope in the CRUD task: conditional update and conditional delete.

Transaction and batch Bundles, including conditional create inside a transaction (`If-None-Exist`), are covered in [fhir-bundles-transactions.md](fhir-bundles-transactions.md).

## Error handling

Write failures use the same `execute()` wrapper as read/search. Connection errors and `BaseServerResponseException` become `FhirClientException`. A missing resource after delete is still an error, not `null`.

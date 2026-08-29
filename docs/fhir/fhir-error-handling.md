# FHIR error handling foundation

This note adds a **bounded, safe error model** around FHIR integration failures. Read it after [fhir-audit-observability.md](fhir-audit-observability.md) and [fhir-metrics-observability.md](fhir-metrics-observability.md). It does not replace mapping, routing, OAuth, SMART, audit, or metrics.

There is still no retry, backoff, circuit breaker, idempotency, or dead-letter queue.

## Why error handling exists

Callers should not depend on HAPI exception types. These failures mean different things operationally:

```text
Patient not found          → NOT_FOUND
FHIR server unavailable    → SERVER_ERROR
OAuth token rejected       → AUTHENTICATION_ERROR
socket timeout             → TIMEOUT
connection refused         → CONNECTION_ERROR
unknown destination        → VALIDATION_ERROR (routing)
```

The job of this task is to **detect, classify, propagate, audit, and count**. It does not automatically call the server again.

## Error model

```text
lab.healthcare.fhir.exception
├── FhirErrorCategory
├── FhirErrorDetails
├── FhirErrorClassifier
└── FhirClientException
```

```text
FhirErrorDetails
 ├── category
 ├── status
 ├── operation
 ├── destination
 ├── resourceType
 ├── resourceId
 └── message          canned safe text
```

`FhirClientException` remains the FHIR operation boundary. It carries `FhirErrorDetails` and keeps the original HAPI/OAuth/network exception as the cause.

## Categories

| Category | Typical source | Safe message |
|---|---|---|
| `VALIDATION_ERROR` | HTTP 400/422, invalid routing destination | `FHIR request is invalid` (routing may say destination not found / disabled) |
| `AUTHENTICATION_ERROR` | HTTP 401, `OAuth2TokenException` | `FHIR authentication failed` |
| `AUTHORIZATION_ERROR` | HTTP 403 | `FHIR authorization failed` |
| `NOT_FOUND` | HTTP 404/410 | `FHIR resource not found` |
| `CONFLICT` | HTTP 409/412 | `FHIR resource conflict` |
| `SERVER_ERROR` | HTTP 429 and 5xx | `FHIR server unavailable` |
| `TIMEOUT` | socket/request timeout, HTTP 408 | `FHIR request timed out` |
| `CONNECTION_ERROR` | connection refused, DNS, unreachable | `FHIR connection failed` |
| `UNKNOWN` | anything else | `FHIR integration failed` |

Do not add a category per HAPI class. Future retry policy will key off this list.

## HTTP / FHIR mapping

```text
400 / other 4xx → VALIDATION_ERROR
401             → AUTHENTICATION_ERROR
403             → AUTHORIZATION_ERROR
404 / 410       → NOT_FOUND
408             → TIMEOUT
409 / 412       → CONFLICT
429 / 5xx       → SERVER_ERROR
```

Status is copied into `FhirErrorDetails.status` when HAPI exposes it. Classification does not invent a status for timeouts or connection failures.

## Connection vs timeout

Both often arrive as HAPI `FhirClientConnectionException` (HAPI subclasses that as `InternalErrorException` / HTTP 500). The classifier special-cases client I/O **before** mapping that 500:

```text
SocketTimeoutException / "timed out"  → TIMEOUT
ConnectException / UnknownHost        → CONNECTION_ERROR
other FhirClientConnectionException   → CONNECTION_ERROR
```

They stay distinct because a later retry task may retry one and not the other. This task does not retry either.

## OAuth

`OAuth2TokenException` stays the token-layer exception (`auth.oauth2`). At the FHIR operation boundary it becomes:

```text
OAuth2TokenException
      ↓
FhirClientException category=AUTHENTICATION_ERROR
message=FHIR authentication failed
cause=OAuth2TokenException
```

The canned message does not include `invalid_client`, token JSON, or secrets. `OAuth2TokenClient` is unchanged.

HTTP 401 from the FHIR server (invalid Bearer) is also `AUTHENTICATION_ERROR`. HTTP 403 (insufficient scope) is `AUTHORIZATION_ERROR`.

## Routing

Routing failures stay `RoutingException`. They are not wrapped as `FhirClientException`, so callers can tell “wrong destination” from “FHIR 404”.

| Routing case | Exception | Category |
|---|---|---|
| unknown profile | `RoutingException` | `VALIDATION_ERROR` |
| disabled profile | `RoutingException` | `VALIDATION_ERROR` |
| invalid request (not a Patient, missing id) | `RoutingException` | `VALIDATION_ERROR` |

The destination name is part of the safe message (`FHIR destination not found: does-not-exist`). There is no fallback to `local-hapi`. `FhirService` still does not know about routing.

## Flow

```text
FHIR operation
      │
      ├── success → audit SUCCESS → metrics success++
      │
      └── exception
             ↓
       FhirErrorClassifier
             ↓
       FhirClientException  or  RoutingException
             ↓
       audit FAILURE (error=category)
       metrics failure++
```

`RoutingService` no longer inspects HAPI types. It reads `details()` from the exception that already crossed the FHIR or routing boundary.

## Audit and metrics

A missing Patient:

```text
FHIR_AUDIT correlationId=abc-123 destination=local-hapi operation=READ resourceType=Patient resourceId=does-not-exist outcome=FAILURE status=404 error=NOT_FOUND durationMs=12
```

Unknown destination:

```text
FHIR_AUDIT … destination=does-not-exist outcome=FAILURE error=VALIDATION_ERROR
```

Metrics still use only bounded dimensions (`operation`, `destination`, `resourceType`, `outcome`). They do **not** label by `NOT_FOUND`, patient id, correlation id, or `OperationOutcome` text.

## Safe messages and causes

External-facing `getMessage()` is the canned text. The original exception remains `getCause()` for diagnostics inside the process.

Not in messages, audit lines, or metric labels:

```text
access_token
client_secret
refresh_token
authorization_code
code_verifier
Bearer …
complete Patient / Observation JSON
complete OperationOutcome / HTTP body
java.net.ConnectException: …
```

## Error handling vs resilience

This task:

```text
detect → classify → wrap safely → audit → count
```

Not this task:

```text
retry, backoff, circuit breaker, idempotency, queue, dead-letter
```

A `503` is `SERVER_ERROR` once. The client is not called again.

## Future

```text
023  Error Handling     (this note)
024  Retry / Backoff
025  Circuit Breaker
026  Idempotency
027  Async Integration
```

Task 024 implements that policy for routed Patient READ; see [fhir-retry-resilience.md](fhir-retry-resilience.md). `NOT_FOUND` and `VALIDATION_ERROR` do not retry; `TIMEOUT`, `CONNECTION_ERROR`, and `SERVER_ERROR` may.

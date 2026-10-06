# ADR-088 — Server-rendered human review demo

## Status

Accepted

## Date

2026-10-06

## Context

The follow-up review queue, case detail, current clinical context and operational close already exist as internal Healthcare AI contracts. A person still cannot operate that loop without an HTTP client. A browser that called those internal routes directly would need `X-Service-Token`.

## Decision

Healthcare AI serves a synthetic review demo as HTML from the same FastAPI process:

```text
GET /review-cases
GET /review-cases/{reviewCaseId}
POST /review-cases/{reviewCaseId}/close
```

This is a presentation component of Healthcare AI. It is not a third product or deployment unit, and it does not add a Node, SPA or separate backend.

The browser receives HTML and posts a close form. It does not receive, store or send `X-Service-Token`. The presentation calls the existing review and clinical-context services in process. It does not proxy arbitrary URLs or FHIR identifiers.

`MODEL_BOUNDARY_SERVICE_TOKEN` protects internal service calls. Human Review form signing uses a separate setting, `HUMAN_REVIEW_FORM_SIGNING_SECRET`. The presentation does not reuse or derive one from the other. A missing or blank signing secret disables the close form and rejects close posts. Neither secret is sent to the browser.

The close form includes a short-lived HMAC over the review case id, expected version and expiry, and the POST must come from the same origin. The HMAC shows that this presentation layer issued those parameters during that window. It is not authentication, not authorization, not single-use, and not replay-proof. Review-case version and closure rules remain authoritative.

Static files for this demo are served only from `app/static/human_review`. That directory is the public asset root for the review pages.

The demo is reachable by anyone who can reach the process. `caseId` is an operational identifier. Patient name, date of birth, MRN and `Patient.id` are not shown. Gemini narrative is not shown. Current clinical context is not stored. A closed case does not gain a historical clinical snapshot. Failure to load the current context does not block operational closure.

Future human IAM stays a separate decision.

## Consequences

Local demo topology remains browser, Healthcare AI, and the configured FHIR endpoint. No new runtime dependency is required. The demo must not be described as production security, compliance, or a user login.

## Non-goals

This decision does not add human login, RBAC, reviewer identity, assignment, notes, patient search, FHIR writes, another protocol, another FHIR resource type, or a generic proxy.

## Related decisions

- [ADR-086](ADR-086-persistent-follow-up-review-workflow-and-operational-authority-boundary.md)
- [ADR-087](ADR-087-case-bound-current-clinical-review-context.md)

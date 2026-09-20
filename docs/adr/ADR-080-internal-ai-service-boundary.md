# ADR-080 — Internal AI Service Boundary

## Status

Proposed

## Date

2026-09-20

## Context

Python exposes three HTTP routes (`app/main.py`). Two are product-relevant internals. C1 found that `GET /internal/agent-context` has **no inbound** `X-Service-Token`, while `POST /internal/experimental-summary` requires it, and Java requires the same header on `GET /api/model-boundary/v1`. Default `AI_SERVICE_HOST` is `0.0.0.0`. C2 marked inbound auth and bind as intention-level decisions, not a vault/gateway choice.

## Current State

| Interface | Provider | Consumer (intended) | Inbound auth | Payload / purpose |
|---|---|---|---|---|
| `GET /api/model-boundary/v1` | Java `ModelBoundaryContractController` | Python `consumer.fetch_contract` | `X-Service-Token`; fail-closed; `MessageDigest.isEqual` | Full v1 JSON; projection counts used by 074 |
| `GET /internal/agent-context` | Python `agent_context` | Local/operator caller | **None** | `AgentContextResult`; `modelCalled=false`; does not return v1 records |
| `POST /internal/experimental-summary` | Python `experimental_summary` | Local/operator caller | `X-Service-Token`; string equality; fail-closed if blank | Exact `SYN-076-001`; Gemini if gate+key |
| `GET /health` | Python | Ops | None | Liveness |

074 may hold the full v1 JSON in memory while deciding `received`/`rejected`; it does not send that JSON to Gemini (ADR-078). 076 does not call Java. Both Python paths may log `X-Correlation-ID` or a generated UUID; Java v1 logging does not use the same scheme. Confirmed: `app/consumer.py`, `app/experimental_service.authenticate`, `ModelBoundaryServiceAuthFilter`.

## Decision

1. **`/internal/*` on the AI Surface is a strictly internal interface**, not a public or partner API. Naming is an intention, not a network control by itself.
2. **074 and 076 stay separate paths** (ADR-078). A caller of `agent-context` is not authorized to invoke Gemini, and vice versa, except by separately meeting each path’s rules.
3. **Service-to-service authentication remains the Java v1 rule** (`X-Service-Token`). Python **must send** that header when calling Java if the token is configured (already implemented).
4. **Architectural intention for inbound Python internals:** untrusted networks must not be able to invoke `/internal/agent-context` or `/internal/experimental-summary` without an explicit service-to-service authentication mechanism and/or an enforced network boundary that makes the interface unreachable from untrusted networks. The path prefix `/internal` is not that boundary. Today 076 requires inbound `X-Service-Token`; 074 has no inbound authentication; `AI_SERVICE_HOST` still defaults to `0.0.0.0`. That gap is acknowledged; **this ADR does not implement a fix** and does not choose IAM, a vault, an API gateway, mTLS, or any other concrete tool.
5. **`GET /health` may remain unauthenticated** for local process checks.

This is an intention and constraint for later implementation ADRs or tasks — not a change to running code.

## Rationale

C1: anyone who can reach `:8090` can trigger a Java v1 fetch if the process already holds `MODEL_BOUNDARY_SERVICE_TOKEN`. C2: that is a decision-now *intention*. Formalizing “internal + secret and/or isolation” without picking tools keeps C3 inside its scope.

## Alternatives Considered

- **Leave 074 public-on-the-port indefinitely.** Lowest friction; largest accidental-trigger surface.
- **Require inbound token on 074 now in this ADR as implemented code.** Would be C3 implementation; forbidden.
- **Depend only on “internal” in the path.** Insufficient (C1 bind default).
- **Introduce OAuth/IAM for these routes.** Out of C3; enterprise identity is a later product decision.

## Consequences

Positive: later work cannot treat `/internal/agent-context` as an open internet API; 074/076 stay distinct.

Negative / trade-off: the documented intention is stricter than current 074 code; until a future change, the gap remains. Shared `MODEL_BOUNDARY_SERVICE_TOKEN` for Java v1 and Python 076 is unchanged (laboratory secret, not IAM).

## Boundaries

No code, YAML, or Docker changes. No vault, gateway, or mTLS product. No merge of 074 and 076. No FHIR → Gemini.

## Related Decisions

- ADR-076 — 076 auth and fixture.
- ADR-078 — data that may cross each hop.
- ADR-081 — runtime bind/packaging is not a substitute for this intention, but complements it.
- `docs/ai-governance/llm-boundary-threats-and-controls.md` (T1, T2).
- Task 074 / Task 075 specs (`docs/tasks/TASK_074_*`, `TASK_075_*`).

## Future Reconsideration

Revisit when packaging exposes `:8090` beyond a single operator workstation, when 074 inbound auth is implemented, or if the two Python routes are split across processes.

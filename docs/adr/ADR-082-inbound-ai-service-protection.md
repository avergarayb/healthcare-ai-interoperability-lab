# ADR-082 — Inbound AI Service Protection

## Status

Proposed

## Date

2026-09-20

## Context

ADR-080 recorded an architectural *intention*: untrusted networks must not invoke Python `/internal/agent-context` or `/internal/experimental-summary` without an explicit service-to-service authentication mechanism and/or an enforced network boundary. The path prefix `/internal` is not that boundary. ADR-080 did not choose a mechanism and did not change running code.

Phase C4.1 asked which principle should fulfill that intention. The material gap is Task 074: anyone who can reach the AI Surface port can trigger a Java `GET /api/model-boundary/v1` fetch if the Python process already holds `MODEL_BOUNDARY_SERVICE_TOKEN`. Task 076 already requires inbound `X-Service-Token`. This ADR states the inbound-protection *requirement*. It does not implement it.

## Current State

Verified on `main` (`app/main.py`, `app/consumer.py`, `app/experimental_service.authenticate`, `app/config.py`, `ModelBoundaryServiceAuthFilter`):

| Interface | Inbound authentication | Effect if the port is reachable |
|---|---|---|
| `GET /internal/agent-context` (074) | None | Calls `consume()` → `fetch_contract`. If the process already has `MODEL_BOUNDARY_SERVICE_TOKEN`, Python sends that header to Java v1. May hold full v1 JSON in memory while deciding `received`/`rejected`. Returns `AgentContextResult` with `modelCalled=false`. Does not call Gemini. |
| `POST /internal/experimental-summary` (076) | `X-Service-Token`; fail-closed if blank; string equality | 401 before the feature gate when auth fails. Gemini only under ADR-076 (fixture `SYN-076-001`, `LLM_EXPERIMENTAL_ENABLED`, API key). Does not call Java. |
| Java `GET /api/model-boundary/v1` | `X-Service-Token`; fail-closed; `MessageDigest.isEqual` | Not a Python route. This is the hop 074 can trigger. |
| `GET /health` | None | `{"status":"ok"}`. No v1, no fixture, no model output. |

`AI_SERVICE_HOST` still defaults to `0.0.0.0` (`config.py`, `.env.example`, README uvicorn `--host 0.0.0.0`). The path `/internal` is a naming convention, not a network control. Threat-model isolation of the Python listener is recorded as absent (`llm-boundary-threats-and-controls.md`).

Intended callers of 074 and 076 remain local/operator callers. Java does not invoke 074. Sharing `MODEL_BOUNDARY_SERVICE_TOKEN` across Java v1 outbound and 076 inbound does not merge the two Python paths (ADR-078, ADR-080).

## Decision

1. **`GET /internal/agent-context` and `POST /internal/experimental-summary` are strictly internal interfaces.** They are not a public API, partner API, EHR API, or end-user API.
2. **Both internal endpoints require service-to-service authentication** of the same architectural *class* already used on Java v1 and 076: an explicit caller credential presented to the AI Surface. This is service authentication, not user IAM.
3. **Both internal endpoints must sit behind an effective network boundary** that makes them unreachable from untrusted networks. The path prefix `/internal` is not that boundary.
4. **The two layers are both required.** Service-to-service authentication does not replace network reachability. Network reachability does not replace authentication. Neither layer is optional because the other exists.
5. **074 must adopt inbound protection of that class.** A request that does not authenticate **must not** start the Java v1 fetch. Possession of `MODEL_BOUNDARY_SERVICE_TOKEN` inside the process is not inbound authentication of the HTTP caller.
6. **076 is unchanged in principle:** inbound `X-Service-Token`, exact fixture `SYN-076-001`, feature gate, application-owned `requiresHumanReview=true`, `modelCalled` only after provider invocation starts, experimental Gemini only. This ADR does not alter those rules.
7. **074 and 076 remain independent paths** (ADR-078). Authenticating for one path does not authorize the other. Sharing the laboratory secret does not merge the paths and does not license FHIR → Gemini or v1 → Gemini.
8. **`GET /health` may remain unauthenticated** as a liveness check. It must not become the security control for 074/076 and must not expose v1, fixture, prompt, completion, or model metadata beyond a simple process status.
9. **This ADR does not implement the requirement** and does not change running code, bind address, Docker, or tests.

## Rationale

C4.1: the 074 gap is an invocation-boundary problem, not a missing product stack. A caller of 074 does not need to present a secret; the process can use a secret it already holds to pull v1. Token-only would close anonymous 074 but would leave a leaked secret usable on an `0.0.0.0` listener. Network-only would depend on a boundary the repository does not currently enforce. Recording both layers as architecture matches ADR-080 without turning the path name, a firewall brand, or an IAM product into the control.

`/health` stays out of that pair because it does not carry contract or model data (ADR-080).

## Alternatives Considered

- **Inbound service token for 074 only.** Would close anonymous Java fetch using the existing laboratory authentication class. It does not by itself make `:8090` unreachable if the listener is exposed and the secret leaks (threat T2). Authentication is required; it is not the whole decision.
- **Network isolation / localhost-only exposure only.** Would help on a workstation if actually enforced. The current default bind is `0.0.0.0`, and isolation is not an implemented control. SaaS or hybrid hops cannot rest on reachability alone. 074 would stay weaker than 076 whenever the bind or firewall is wrong.
- **Token plus effective network boundary.** This ADR records that combination as the architectural requirement. It is a principle (authenticated caller **and** untrusted networks cannot reach the internals), not a choice of Vault, gateway, mTLS, or Kubernetes NetworkPolicy.
- **Leave 074 unauthenticated on the port.** Lowest local friction; largest accidental-trigger surface. Rejected: it leaves ADR-080 unfulfilled and lets any reachable caller drive the Java hop.
- **Introduce IAM, OAuth, Spring Security, Vault, an API gateway, mTLS, or a service mesh in this ADR.** Those are later implementation or infrastructure decisions. They are not required to *state* that internals need service authentication and an effective network boundary. This ADR does not select them.

## Consequences

Positive: later work cannot treat 074 as an open-on-the-port trigger; 076 stays gated; `/internal` cannot be cited as a control; packaging (ADR-083) cannot be used as a substitute for inbound protection.

Negative / trade-off: the documented requirement remains stricter than current 074 code until a later implementation change. The laboratory shared secret and Python string comparison are unchanged. How the network layer is enforced per environment is deferred.

## Boundaries

No code, YAML, Docker, or test changes. No change to `AI_SERVICE_HOST` or a bind to `127.0.0.1`. No Spring Security, OAuth, IAM, Vault, API gateway, mTLS, service mesh, Kubernetes, concrete firewall, secret rotation, or rate limiting. No split of 074/076 into separate processes. No merge of 074 and 076. No FHIR → Gemini and no v1 → Gemini.

## Related Decisions

- ADR-076 — Controlled Gemini integration (076 auth, fixture, gates; do not modify).
- ADR-078 — FHIR and AI Boundary (074 ≠ 076; v1 is not model input).
- ADR-080 — Internal AI Service Boundary (intention this ADR turns into a requirement).
- ADR-081 / ADR-083 — packaging and network placement complement this ADR; they do not replace inbound authentication.
- `docs/ai-governance/llm-boundary-threats-and-controls.md` (T1, T2; network isolation recorded as absent).
- `docs/ai-governance/product-governance-boundary.md` (G0/G1 current; G2/G3 not entered).

## Future Reconsideration

Revisit when 074 inbound authentication is implemented, when `:8090` is exposed beyond a single operator workstation, if 074/076 are split across processes, or if a later ADR introduces a secret manager, per-caller identity, or transport authentication. Authenticating 074 does not authorize G3 (clinical-context AI).

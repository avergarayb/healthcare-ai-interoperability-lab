# ADR-104 — Longitudinal laboratory comparison

## Status

Accepted for this laboratory increment. It does not authorize diagnosis, a live provider call, unit conversion, or cross-border exchange.

## Context

The jurisdiction demonstration already returns an undated synthetic seed through one Clinical Federation. A second clinical case needs two dates for one indicator. The summary contract counts that seed exactly, so the dated pair cannot be added to the summary observation list.

## Decision

1. The same jurisdiction connector appends one dated pair tagged `longitudinal-series`. The summary minimizer skips that tag. The original seed ids and values stay unchanged.
2. One deterministic engine compares the pair. `effectiveDateTime` is the only accepted clinical date. `issued` is ignored. `effectivePeriod` and any other date form deny that comparison.
3. The same LangGraph and the same NeutralModelGateway method serve Peru and Spain. The server-selected profile supplies the organization, jurisdiction, and policy. The new operation is `longitudinal-lab-comparison-v1`.
4. Ledger schema 9 adds that operation with `pe-longitudinal-lab-policy-v1` or `es-longitudinal-lab-policy-v1`. Schema 8 does not accept those pairs. A summary permit cannot spend this operation.
5. The model may describe the calculated change. It may not replace the values, dates, unit, difference, or references. The evidence row is written from the resources and the engine.
6. The dashboard gains one section, shown only when that evidence exists. Approval and rejection stay on the existing decision path.
7. The model transport stays intercepted. `request_real_provider_send()` stays closed.

## Consequences

Peru and Spain can demonstrate a dated comparison without a second federation or a second gateway. The comparison does not diagnose, predict disease, convert units, or certify RENHICE, HCDSNS, or EHDS.

## References

- [longitudinal-lab-comparison-v1](../contracts/longitudinal-lab-comparison-v1.md)
- [jurisdiction-lab-demo-v1](../contracts/jurisdiction-lab-demo-v1.md)

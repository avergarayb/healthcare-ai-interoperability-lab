# ADR-098 — Lab result summary operation

## Status

Accepted for this laboratory increment. Not a production authorization and not a change to follow-up Human Review.

## Decision

The durable permit catalog accepts one additional pair: operation `lab-result-summary-v1` with policy `lab-result-summary-policy-v1`. Every other operation remains `invalid_input`. `vacation-days-v1` stays on `model-gateway-policy-v1`. The same gateway class executes the clinical call. It does not reuse the vacation document, the vacation consent, or the vacation adapter.

The model result is queued as pending. The follow-up review table is unchanged because its trigger must already be a matched follow-up protocol. A lab summary is not that protocol.

## Consequences

A second active permit can exist for the same principal only when the operation differs. A held clinical reservation is not released on failure and is not reused. Docker remains required for a live Mini HIS and Mini LIS read. The automated tests use the real federation client with an intercepted transport.

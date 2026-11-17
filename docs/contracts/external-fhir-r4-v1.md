# External FHIR R4 v1

Laboratory read of one public synthetic FHIR R4 sandbox. This contract does not change [Clinical Federation v1](clinical-federation-v1.md). It does not authorize Epic, Oracle, a write, a model-chosen URL, or a real LLM call.

## Origin

| Field | Value |
|---|---|
| Source key | `smart-sandbox` |
| Organization | `org-smart-sandbox` |
| Base URL | `https://r4.smarthealthit.org` |
| Allowed host | `r4.smarthealthit.org` |
| FHIR version accepted | `4.0.` prefix from CapabilityStatement |
| Caller | `mini-his` |
| Local patient system | `https://lab.local/external-fhir/patient` |
| Local patient value | `EXT-PAT-001` |
| Switch | `external-fhir.enabled`, default `false` |

The checked-in grant list remains `mini-his` and `mini-lis`. When the switch is on, the process adds `smart-sandbox` to the `mini-his` grant and marks it explicit-only. A request that omits `sources` does not read it. A request that names it without the link returns `identity_unresolved` and does not call the sandbox.

Identifier equality and name equality are not a link. The link is one SQLite row outside Mini HIS and Mini LIS: caller system, identifier system, identifier value, destination system, destination logical id. The destination id is discovered from the sandbox at read time. It is not assumed to survive a sandbox reset.

## Reader

The Java client sends HTTPS GET only, with the platform TLS trust store and `Redirect.NEVER`. It does not send a credential. Timeouts, a 1 MiB body cap, two pages, and twenty entries per page are closed. The first query is built by the client. A later page is accepted only when it is `https`, the allowlisted host, portless, and without userinfo. It must either stay on the same resource path and name the same patient, or be that host's `_getpages` continuation on `/` with no patient parameter. A parameter value that contains `://` is rejected. An IP host is rejected. The federation Observation read uses the closed laboratory quantity query.

HTTP 401, 403, 429, 500, a timeout, and a rejected redirect or body become the federation outcome `unavailable` with `unauthorized`, `forbidden`, `rate_limited`, `source_error`, `timeout`, `redirect_rejected`, or `response_rejected`. HTTP 404 on the patient read is `identity_unresolved`. There is no retry.

An Observation is kept only when `status` is a FHIR R4 observation status and `subject.reference` is `Patient/{id}` or exactly `https://r4.smarthealthit.org/Patient/{id}`. The minimizer accepts those two forms and rejects a second logical id or any other host. `valueQuantity` is tagged `quantity-verified` only when `system` is `http://unitsofmeasure.org`, `code` is present, `value` is numeric, and `unit` is empty or equal to `code`. Any other quantity is tagged `unit-not-verified` and is not converted. A reference range is tagged `range-verified` only when both bounds exist, use that same UCUM code, and low is less than or equal to high. Otherwise a present range is `range-not-verified`. The tag system is `https://lab.local/external-fhir/verification`.

The audit row stores correlation id, method `GET`, host, the resource collection path, HTTP status, outcome, and resource type. The path keeps `/Observation` or `/Patient` and drops the logical id. The row does not store a patient identifier, a resource id, the query string, the body, a name, or a token.

If a next link remains after the page cap, the connector reports truncation. Federation then returns `partial`. That chart is not given to the model. A display unit that differs from the UCUM code, such as `copies/mL` beside `{copies}/mL`, stays `unit-not-verified` and is not converted.

## AI operation

| Field | Value |
|---|---|
| Operation | `external-fhir-lab-summary-v1` |
| Policy | `external-fhir-lab-summary-policy-v1` |
| Tool | `read_external_fhir_chart` |
| Patient | `EXT-PAT-001` |
| Source required | `smart-sandbox` complete |

This operation is not `lab-result-summary-v1` and it is not `vacation-days-v1`. Ledger schema 7 adds this pair. Schema 6 still accepts only the two earlier pairs. A permit for one operation cannot be spent on another. The organization is `org-smart-sandbox`. It is not inferred from the patient id.

The graph calls `NeutralModelGateway.execute_external_summary`. It does not import a provider SDK. The gateway uses the existing Gemini adapter and deployment `gemini-sdk-a`. Another provider stays inactive. One authorization produces one model invocation. An uncertain or failed result is not retried. The reservation stays held when consume does not run. A second use of the same authorization is `replay_denied`.

`GEMINI_API_KEY` in the environment is not permission to send. Consent is issued only with the closed phrase, the external patient, the external organization, and an injected HTTP client. Without that client the result is `provider_send_blocked`. `request_real_provider_send()` also raises `provider_send_blocked`. The laboratory path uses an intercepted client. The receipt phase is `intercepted`. The dashboard states that this is not a response from the real provider.

A missing permit, another operation's permit, a consumed permit, a budget below the reservation, a partial or truncated envelope, an unresolved patient link, an unverifiable UCUM unit, two patient references, an invalid model body, or a citation that is not in the chart denies generation. No review is queued in those cases. The queued review stays `pending` until a person decides it. The graph cannot approve it.

The tool posts the existing federation contract to the Java base URL. It rejects a client whose source list is not exactly `smart-sandbox`, a client aimed at the sandbox host, and any argument other than the bound patient id. The model cannot supply an endpoint.

The model chart keeps at most eight final observations that the Java tag and a second UCUM check both accept. An unverified quantity is omitted. The chart keys are source, resource type, id, status, code, value, and unit. Names and birth dates are dropped. A summary is accepted only when every citation exists in that chart, the observation value appears in the statement, and `review` is `pending_human_review`.

Human Review stores that summary through the existing pending row. The page shows the provider, model, phase `intercepted`, operation, organization, `smart-sandbox`, the cited observations, and status `pending`. The review is associated with `org-smart-sandbox` in the separate organization table. A reviewer bound to another organization cannot open it. A `clinical-auditor` can read it and cannot decide it. The decision requires the IAM CSRF field. A second decision is HTTP 409. The original summary row stays pending.

| Control | Result when it fails |
|---|---|
| Source explicitly `smart-sandbox` and envelope `complete` | `context_incomplete` or `context_rejected` |
| Trusted link for `EXT-PAT-001` in `org-smart-sandbox` | `context_incomplete` |
| One patient reference and verified UCUM | `context_rejected` or the fact is omitted |
| Exclusive durable permit and budget | `not_granted`, `operation_denied`, `budget_exceeded`, or `replay_denied` |
| Injected client and disarmed real send | `provider_send_blocked` |
| Citations exist in the chart | `invalid_output` |
| OIDC reviewer of `org-smart-sandbox` | HTTP 403 |
| One human decision | HTTP 409 |

## Demonstration

1. Set `EXTERNAL_FHIR_ENABLED=true` for the Java process only.
2. Insert the link from `EXT-PAT-001` to a patient id returned by the sandbox in the same run.
3. POST federation `sources: ["smart-sandbox"]` as `mini-his`.
4. Register one schema-7 permit for `external-fhir-lab-summary-v1` and `org-smart-sandbox`. Do not reuse a clinical or vacation permit.
5. Run the external graph with an intercepted Gemini client. Do not call `request_real_provider_send()`.
6. Open the queued review as a `clinical-reviewer` bound to `org-smart-sandbox`. Confirm phase `intercepted`, source `smart-sandbox`, and status `pending`.

## One real Gemini request

This procedure was not executed in E2E-EXTERNAL-001. It stays blocked.

Before any later send, all of the following have to be true:

1. A new Product Owner authorization names this one request.
2. The source data is confirmed synthetic.
3. The exact outbound payload is inspected and contains no name, birth date, address, personal identifier, token, or unverified observation.
4. The budget ceiling and the one reservation are explicit. The reservation is not an existing clinical or vacation row.
5. The provider is `gemini` and the model is `gemini-3.5-flash-lite`.
6. `request_real_provider_send()` is still changed by that later authorization. Until then it raises `provider_send_blocked`.
7. The send mechanism allows one request and does not retry.

Presence of `GEMINI_API_KEY` does not satisfy any of these gates.

## Limits

The sandbox is public, synthetic, and not a production FHIR server. It advertises write interactions. This contract uses read and search-type only. Logical ids can change. A failed or unsuitable sandbox is a blocker, not a reason to replace the origin with a fixture and still call the result a live read. Automated tests use an intercepted server. The live read is a separate test.

# DEMO_EXPERIENCE_V1

## Status

Implemented laboratory contract for the synthetic Human Review demonstration. Slice 1, slice 2, and slice 3 are complete. Automated tests passed. Manual validation of slice 1 is complete. Visual validation of slice 2 is still pending. Not a complete localization. Not production-ready. Not a clinical diagnosis, recommendation, or treatment decision. Not verified clinical identity. Not clinician authorization. Not a security audit. Not IAM, SSO, or RBAC.

This contract changes only the server-rendered words and grouping on the existing queue and case pages. It does not change the behavior or authority of [HUMAN_IDENTITY_V1](human-identity-v1.md). Slice 3 adds only a later documentary reference to [HUMAN_ATTRIBUTION_V1](human-attribution-v1.md) and ADR-094. [CONTROLLED_ACTION_V1](controlled-action-v1.md), [AI_ASSISTED_REVIEW_V1](ai-assisted-review-v1.md), and [the operational review workflow](follow-up-review-workflow-v1.md) stay in force. Stored values, protocol evaluation, coordination policy, and review outcomes do not change.

## Authority

| Source | Owns |
|---|---|
| Durable review case | Status, outcome, version, protocol id, reason codes, matched resources, and event timestamps |
| Current clinical-context read | Encounter, observation, and appointment facts already defined for an open case |
| Stored development attribution | Whether a synthetic principal was recorded for a UI close or a first coordination request |
| This contract | Spanish operational labels, readable UTC dates, and which of those facts stay in the technical-details group |
| Browser | Nothing about protocol, outcome, status, or principal |

Presentation does not create, close, or update a review case. It does not insert a coordination request. It does not call Gemini, institutional retrieval, or FHIR.

## Purpose

A person who is not a developer can read the synthetic Human Review queue and case page and answer three questions:

- what operational situation was recorded;
- why the case is waiting for human review;
- what operational action was recorded, including that a planned coordination is not yet a stored request.

The page continues to say that the laboratory is synthetic and that the development principal is not a verified clinical identity.

## Scope

In scope:

- `GET /review-cases`
- `GET /review-cases/{reviewCaseId}`
- the same case page after a close or after a coordination POST redirects back to it

The HTML language of those two pages becomes `es`.

Out of scope, and left as they are today:

- `GET` and `POST /review-login`, logout, and their English copy, including `Sign in`
- the AI-assisted review section, including `AI-assisted review`, `Generate AI assistance`, `Not generated.`, the existing disclaimer, and neutral assistance messages
- `REASON_EXPLANATIONS` in `review_reason_explanations.py`, because that table is also the model projection
- internal JSON routes, form field names, HMAC, sessions, and service-token authentication
- protocols, policies, outcome enums, case statuses, coordination status, migrations, and stored rows

This is not a localization of Healthcare AI.

## What stays easy to see

Operational history and development attribution stay outside `Detalles técnicos`. A reader does not open that group to see them.

The history section heading is `Historial operativo`. Each row shows the event, the previous status, the new status, the outcome label when one exists, and the readable UTC time. Event labels are `Creado` and `Cerrado`. Status labels are `Abierto` and `Cerrado`. An absent value is `Ninguno`.

The attribution section heading is `Atribución de desarrollo`. It always includes:

`Los identificadores mostrados son principales sintéticos de desarrollo, no una identidad clínica verificada.`

Closure lines:

| Stored state | Visible sentence |
|---|---|
| Case open | `Cierre del caso: aún no está cerrado.` |
| Case closed, no `review_case_closed` row | `Cierre del caso: no se registró atribución de desarrollo.` |
| Case closed, with that row | `Cierre del caso: principal sintético de desarrollo {principal_id}. Registrado {readable UTC}.` |

`{principal_id}` is the stored value, unchanged. The attribution section does not say that a coordination request is absent. That would contradict a planned coordination that is still waiting to be recorded.

When a coordination row exists, its development-attribution line stays once, inside the coordination section, not as a second request:

| Stored state | Visible sentence |
|---|---|
| No `coordination_request_created` row | `No se registró atribución de desarrollo para esta operación.` |
| With that row | `Principal sintético de desarrollo {principal_id}. Registrado {readable UTC}.` |

Session ids, cookie values, secrets, and token hashes stay absent from the HTML.

## Operational sentences

These three sentences are exact. They are not clinical recommendations and they do not say that a message was sent, FHIR was written, or an appointment was booked.

| Condition | Sentence, shown once |
|---|---|
| Outcome `follow_up_coordination_planned` and no coordination row | `Coordinación interna planificada. Solicitud pendiente de registro.` |
| A coordination row exists | `Solicitud interna de coordinación registrada.` |
| Outcome `review_completed_no_operational_action` | `Revisión finalizada sin acción operativa registrada.` |

An open case has no outcome and cannot have a coordination row. Its close form offers the first sentence for `follow_up_coordination_planned` and the third sentence for `review_completed_no_operational_action`. The posted values remain those two outcome strings.

After closure, the outcome section shows the first or the third sentence. When a coordination row exists, the first sentence is not shown. The coordination section shows the second sentence. The stored outcome remains `follow_up_coordination_planned` and appears in technical details.

The coordination section also shows this standing sentence when a row exists:

`Esto no envía un mensaje, no escribe FHIR y no agenda una cita.`

The section heading is `Solicitud de coordinación interna`. The button on an eligible case without a row remains a second explicit POST and reads `Registrar solicitud de coordinación interna`. Closing the case still does not create the request.

## Queue

Heading `Casos abiertos`. Intro `Casos de revisión abiertos, del más antiguo al más reciente.` Empty state `No hay casos de revisión abiertos.`

| Column | Operational text | Technical text on the next line of the same cell |
|---|---|---|
| Caso | The existing `caseId` link | None |
| Motivo de revisión | Spanish protocol label | The stored protocol id |
| Creado | Readable UTC | The stored timestamp, unchanged |
| Estado | `Abierto` | `open` |

Protocol labels:

| Stored protocol id | Label |
|---|---|
| `POST_CONSULTATION_RESULT_REVIEW_V1` | `Revisión de un resultado posterior a la consulta` |
| `MISSED_FOLLOW_UP_REVIEW_V1` | `Revisión de un seguimiento no realizado` |

An unknown protocol id is shown as itself, with no invented label. Queue order, page size, and the older-cases link stay as they are. The older-cases link reads `Casos más antiguos`. Refresh reads `Actualizar la cola`.

## Case page

Above technical details, in this order:

1. Synthetic-demo banner.
2. Link `Cola de revisión`.
3. Operational summary: case id, status label, readable created time, and readable closed time when closed. The operational sentence is not repeated in this summary.
4. Why the case is in review: Spanish protocol label and the Spanish reason below. The lead sentence for a matched rule is `La regla operativa de revisión se cumplió. Esto no es un diagnóstico ni una recomendación clínica.`
5. Current clinical context, with the same facts as today and the labels in this contract.
6. `Historial operativo`.
7. `Atribución de desarrollo`.
8. The unchanged AI-assisted review section.
9. The close form, or the closed outcome sentence.
10. The coordination section when the case is eligible or a row exists.

Reason labels, used only on this page:

| Reason code | Label |
|---|---|
| `post_consultation_result_requires_review` | `Quedó registrado un resultado posterior a la consulta y el caso se abrió para revisión humana.` |
| `missed_follow_up_without_confirmed_replacement` | `La cita de seguimiento no se completó y, al crear el caso, no había otra cita futura confirmada.` |

The banner is:

`Demostración sintética de laboratorio. Estas páginas exigen una sesión de desarrollo. Esa sesión no es una identidad clínica verificada, ni IAM, ni SSO, ni acceso por roles. El identificador del caso es operativo y no es la identidad del paciente.`

Context copy:

| Current English | Replacement |
|---|---|
| Current clinical context is a current read. It does not re-run the original protocol. | `El contexto clínico actual es una lectura de ahora. No vuelve a ejecutar la regla que creó el caso.` |
| Patient identity is not shown in this view. | `La identidad del paciente no se muestra.` |
| Current clinical context is temporarily unavailable. | `El contexto clínico actual no está disponible en este momento.` |
| Current clinical context is not available for a closed case. | `El contexto clínico actual no se muestra cuando el caso está cerrado.` |

The close form still says that the choice is an operational outcome and not a diagnosis or a treatment decision:

`Esto registra un resultado operativo de la revisión. No es un diagnóstico ni una decisión de tratamiento.`

The submit button reads `Cerrar la revisión`.

## Technical details

One `Detalles técnicos` group, closed until the reader opens it, contains the original facts for that page:

- protocol id
- evaluation status, including `matched`
- reason codes
- matched resource references, the current technical provenance
- case version
- raw status and outcome values
- raw event types `created` and `closed`
- every stored timestamp in its original form
- encounter, observation, and appointment technical references
- raw appointment status values and classification codes, including `OTHER`
- coordination request id and raw status `requested`, when a row exists

Opening or leaving this group closed does not reload the page and does not call FHIR.

## Readable UTC

A stored timestamp that matches the current review timestamp form is shown as `D de mes de YYYY, HH:MM:SS UTC`. The month names are the Spanish names `enero` through `diciembre`. Fractional seconds are not added to this sentence. The original string, including fractional seconds and the trailing `Z`, is shown unchanged in technical details and on the queue's technical line.

The clock is not shifted to a local zone. A timestamp that does not match that form is shown unchanged, with no invented readable sentence.

## Appointments

Current appointment classification labels:

| Code | Label |
|---|---|
| `NONE` | `No se obtuvo ninguna cita.` |
| `UPCOMING_CONFIRMED` | `Próxima y confirmada` |
| `UPCOMING_UNCONFIRMED` | `Próxima y no confirmada` |
| `CANCELLED` | `Cancelada` |
| `PAST` | `Pasada` |
| `OTHER` | `Estado operativo de la cita no clasificado` |

`OTHER` remains the stored classification for a status and start combination that the current rules do not place in the other four labels, including `noshow`. The label does not say that the appointment was rescheduled or that follow-up is clinically necessary.

For a missed-follow-up case, the triggering appointment is rendered once, as `Cita que originó el caso`. The current appointment list does not render that same reference again. When that omission is the reason an item is absent, the list says `La cita que originó este caso está arriba.` The classification summary is still shown once. A post-consultation case does not gain a triggering-appointment block.

## Implementation slices

Slice 1 is labels, readable dates, the technical-details group, and the coordination sentences. History and attribution stay outside that group. Appointments stay on their current duplication behavior until slice 2.

Slice 2 removes the repeated triggering appointment and replaces `Other appointment status`.

Slice 3 adds one forward-looking status sentence to [HUMAN_IDENTITY_V1](human-identity-v1.md) and [ADR-093](../adr/ADR-093-human-review-session.md). Those documents still record that the identity contract did not implement attribution. The new sentence says that laboratory attribution was later accepted by [HUMAN_ATTRIBUTION_V1](human-attribution-v1.md) and ADR-094, and that security audit remains deferred. Slice 3 does not change runtime behavior.

## Slice 1 acceptance

Automated:

- The queue shows `Revisión de un resultado posterior a la consulta` and `POST_CONSULTATION_RESULT_REVIEW_V1` for that protocol, and the missed-follow-up pair for the other.
- A stored timestamp appears both as the readable UTC sentence and as the original string.
- `La regla operativa de revisión se cumplió. Esto no es un diagnóstico ni una recomendación clínica.` is outside `Detalles técnicos`. The string `matched` is inside that group.
- Matched resource references are inside that group.
- `Historial operativo` and `Atribución de desarrollo` are outside that group.
- An open close form offers the pending-registration sentence and the no-action sentence, and still posts the existing outcome values.
- A closed planned case without a coordination row shows the pending-registration sentence once.
- A page with a coordination row shows `Solicitud interna de coordinación registrada.` once and does not show `Solicitud pendiente de registro.`
- A no-action closure shows `Revisión finalizada sin acción operativa registrada.`
- The development-principal warning remains, and a historical case still says that no development attribution was recorded.
- The HTML does not contain the signing secret, the service token, the session cookie, or the session id.
- `REASON_EXPLANATIONS` is unchanged.
- The login page still contains `Sign in`.
- The assistance section still contains `AI-assisted review`.

Manual:

- On the queue and on one open case, a reader can say what was recorded and why it is in human review without opening technical details.
- On a closed case, history and attribution are visible without opening technical details.
- The banner is visible and still says that the session is not a verified clinical identity.
- Opening technical details shows the original protocol id, `matched`, the ISO timestamp, and the technical provenance.

## Slice 2 acceptance

Automated:

- A missed-follow-up page includes the triggering appointment reference once in the appointment presentation.
- `Other appointment status` is absent.
- `Estado operativo de la cita no clasificado` is present when the current classification is `OTHER`.
- `OTHER` remains inside technical details.
- A post-consultation page still shows its encounter and observation sections and does not show `Cita que originó el caso`.

Manual:

- The originating missed appointment is understandable once, and the current-appointment list points back to it instead of repeating it.

## Slice 3 acceptance

No new runtime test. The existing deterministic suite remains the behavior check.

Automated check of the diff: only `docs/contracts/human-identity-v1.md` and `docs/adr/ADR-093-human-review-session.md` change, and both name `HUMAN_ATTRIBUTION_V1` while still saying that security audit remains deferred.

Manual:

- The identity contract still says that its own version does not store attribution.
- ADR-093 still says that a development session is not attribution and is not a security audit.
- Both documents point forward to the accepted attribution contract without deleting the original decision.

## Non-goals

No translation of login or AI assistance. No second copy of `REASON_EXPLANATIONS` for the model. No change to protocol evaluation, reason codes, outcomes, case status, coordination status, or stored attribution. No backfill. No FHIR write. No new frontend runtime. No change to who may close a case or record a request. No claim of clinical certification, HIPAA, or GDPR.

## Risks

A shorter coordination sentence can still be read as an external action. The standing sentence next to a recorded request is there to prevent that reading.

The page will mix Spanish operational copy with the unchanged English assistance section and the English login page.

A display map that drifts from `REASON_EXPLANATIONS` would tell the reader and the model different stories. Slice 1 keeps the shared English table byte-for-byte and tests the Spanish page sentences separately.

A readable date that shifts the clock, or that drops the original string, would hide the stored instant. This contract forbids both.

Hiding `matched`, protocol ids, or provenance outside technical details would look like those facts were removed. They stay in that group and on the queue's technical line.

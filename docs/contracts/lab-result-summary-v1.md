# LAB_RESULT_SUMMARY_V1

Laboratory contract for one synthetic lab summary. It is not a diagnosis, a treatment decision, or an accepted clinical action.

The operation id is `lab-result-summary-v1`. The policy ref is `lab-result-summary-policy-v1`. A `vacation-days-v1` permit cannot spend this operation, and this permit cannot spend the vacation fixture.

## Sources

The chart is read through the existing Java Clinical Federation client. Python does not call Mini HIS or Mini LIS. Both `mini-his` and `mini-lis` must be `complete`. A partial envelope is denied. The model context keeps final `Observation` and `DiagnosticReport` facts: source, id, code, value, and unit. Patient names, birth dates, addresses, and telecom are not copied.

## MCP

`read_federated_lab_chart` is the only tool. It speaks MCP `initialize`, `tools/list`, and `tools/call`. The process grant supplies the patient and the authorization. Tool arguments cannot widen that grant. Each call is audited. If the audit write fails, the tool returns no chart.

## Model and review

The summary is one Gemini call through `NeutralModelGateway.execute_lab_summary`, using the existing durable permit, reservation, and one-shot transport. There is no automatic retry. The structured result may cite only facts present in the minimized chart. It is stored as `pending`. This flow does not write `follow_up_review_cases`, because that store accepts only a matched follow-up protocol. Nothing in the graph records an acceptance.

A separate laboratory page can record one later human decision, `approved` or `rejected`. That decision is a new row. It does not update the original summary, does not call a model, and does not publish anything to Mini HIS, Mini LIS, or a FHIR server. The reviewer is the development-session principal already resolved by the server. A role posted by the browser is not accepted. The model principal cannot decide. This session is a local demonstration control, not production clinician authentication.

Reading the queue does not create tables. `prepare_decision_store` is the explicit schema step for `lab_summary_decision` and its audit. A decision is rejected with `schema_unprepared` until that step has run. Production must run it deliberately. It is not a migration performed by GET.

The laboratory page may filter the stored rows by patient, review id, authorization id, and decision. Counts are the stored rows. The page does not parse a model sentence into a quantity. A cited observation shows value, unit, code, and a numeric range as a verified quantity only when those fields are stored with a coherent UCUM system. A stored value or unit without that coherent system is shown as recorded and labeled unverifiable; it is not converted or corrected. A field that is not stored is labeled absent. When the stored model sentence contains `GLU 141 mmol/L`, the page states that this is historical model text and that the unit written there is not semantically validated.

The stored model sentence is not reinterpreted. For the historical synthetic LIS observation behind `GLU 141 mmol/L`, `valueQuantity.value` is 141 and `valueQuantity.unit` is `mmol/L`. `valueQuantity.system` and `valueQuantity.code` are absent. The observation code is `GLU` in `https://lab.local/mini-lis/test`, and the reference range is the text `70-110`. No unit conversion is applied. The paired hemoglobin observation is separate: value 13.4, unit `g/dL`, system `http://unitsofmeasure.org`, and quantity code `g/dL`. That stored sentence, its receipt, and its review row stay as recorded.

A later model context accepts an Observation only when `valueQuantity.system` is `http://unitsofmeasure.org`, `valueQuantity.code` is present, and `valueQuantity.unit` matches that code, or matches the registered display `mmHg` for code `mm[Hg]`. Numeric `referenceRange.low` and `referenceRange.high` must use that same system, code, and unit, and low must not exceed high. A text-only range does not by itself block a coded quantity. An observation that fails the check is omitted. If either source then has no Observation, the chart is `context_incomplete`. The minimizer does not convert values. The Mini LIS seed stores GLU as `90` `mg/dL` with range text `70-99`. Payloads that posted GLU `141` with unit `mmol/L` now post `mg/dL` and keep the number `141`. `mmol/L` is not in `mini-lis-ucum-v1`, so an observation that still carries that unit without a code is not sent to the model.

## Live demo

The manual command is not part of the automated tests. It requires a running Clinical Federation endpoint, `GEMINI_API_KEY`, and the clinical confirmation phrase. It does not start Mini HIS, Mini LIS, PostgreSQL, or HAPI.

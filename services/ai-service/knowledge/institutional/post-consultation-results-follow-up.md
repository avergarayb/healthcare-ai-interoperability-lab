```json
{
  "documentId": "post-consultation-results-follow-up",
  "title": "Post-Consultation Results Follow-up Protocol",
  "version": "1.0",
  "status": "active",
  "effectiveDate": "2026-10-06",
  "sourceType": "synthetic_institutional_procedure",
  "synthetic": true,
  "protocolIds": ["POST_CONSULTATION_RESULT_REVIEW_V1"],
  "language": "en"
}
```
# Post-Consultation Results Follow-up Protocol

Synthetic demonstration material. Not validated clinical guidance.

## Purpose

This procedure describes operational handling when a result available after consultation is already waiting for human review. It supports post consultation result follow-up.

## Scope

It applies only to synthetic demonstration operations for post consultation result follow-up. It does not read a patient record and it does not change a review case.

## Operational Trigger

The deterministic protocol has already required human review for a result available after consultation. This procedure does not decide that match and it does not execute the protocol.

## Review Procedure

Confirm that human review is already required. Check whether the deterministic protocol already recorded a confirmed future follow-up. When coordination is still needed, plan follow-up coordination. When no operational action remains, record that the review is completed without operational action. Leave protocol output and review case identity unchanged.

## Human Authority

A person holds human authority over the operational outcome. The procedure does not assign that authority to a model.

## Outcomes

The named operational outcomes are follow-up coordination planned and review completed without operational action.

## Non-goals

This procedure does not interpret clinical meaning, execute the deterministic protocol, redefine its rules, create a review case, or close a review case.

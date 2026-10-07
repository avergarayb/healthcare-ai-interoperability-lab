```json
{
  "documentId": "care-coordination-procedures",
  "title": "Care Coordination Procedures",
  "version": "1.0",
  "status": "active",
  "effectiveDate": "2026-10-06",
  "sourceType": "synthetic_institutional_procedure",
  "synthetic": true,
  "protocolIds": [
    "POST_CONSULTATION_RESULT_REVIEW_V1",
    "MISSED_FOLLOW_UP_REVIEW_V1"
  ],
  "language": "en"
}
```
# Care Coordination Procedures

Synthetic demonstration material. Not validated clinical guidance.

## Purpose

This procedure describes care coordination for follow-up work that is already in human review.

## Scope

It applies to care coordination shared by post consultation result follow-up and missed follow-up appointment handling. It does not detect either condition.

## Operational Trigger

This procedure has no separate detection trigger. Care coordination applies only after a deterministic protocol has already placed the work in human review. The protocol remains the authority for whether review is required.

## Review Procedure

Confirm the work is already in human review. Coordinate the operational next step with the responsible person. The coordination step may lead to follow-up coordination planned or to review completed without operational action. Do not change the protocol result.

## Human Authority

A person holds human authority for care coordination decisions. The procedure does not assign that authority to a model.

## Outcomes

The named operational outcomes are follow-up coordination planned and review completed without operational action. Care coordination does not add another outcome.

## Non-goals

This procedure does not detect a result available after consultation, does not detect a missed follow-up appointment, and does not execute or redefine either deterministic protocol. It does not create a review case or close a review case.

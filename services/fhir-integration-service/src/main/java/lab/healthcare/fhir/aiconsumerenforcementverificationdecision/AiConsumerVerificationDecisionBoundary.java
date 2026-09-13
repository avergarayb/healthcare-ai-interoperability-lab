package lab.healthcare.fhir.aiconsumerenforcementverificationdecision;

import lab.healthcare.fhir.aiconsumerenforcementverification.AiConsumerClinicalDataEnforcementExecutionVerificationResult;

/**
 * Deny-by-default clinical data-access enforcement verification-decision
 * boundary. A verification result is not a decision and a decision is
 * not a grant. Task 072 never reads FHIR.
 */
public final class AiConsumerVerificationDecisionBoundary {

    private AiConsumerVerificationDecisionBoundary() {
    }

    public static AiConsumerVerificationDecisionResult evaluate(
            AiConsumerClinicalDataEnforcementExecutionVerificationResult verification) {
        if (verification == null) {
            return missingVerification();
        }
        return evaluate(AiConsumerVerificationDecisionInput.from(verification));
    }

    public static AiConsumerVerificationDecisionResult evaluate(
            AiConsumerClinicalDataEnforcementExecutionVerificationResult verification,
            VerificationDecisionContext decision) {
        if (verification == null) {
            return missingVerification();
        }
        return evaluate(AiConsumerVerificationDecisionInput.of(verification, decision));
    }

    public static AiConsumerVerificationDecisionResult evaluate(AiConsumerVerificationDecisionInput input) {
        if (input == null || !input.verificationResultPresent()) {
            return missingVerification();
        }
        VerificationDecisionContext decision =
                input.decision() == null ? VerificationDecisionContext.laboratory() : input.decision();
        if (untrustedAssertion(input, decision)) {
            return result(
                    AiConsumerVerificationDecisionStatus.DECISION_BLOCKED,
                    AiConsumerVerificationDecisionReasonCodes.UNTRUSTED_DECISION_ASSERTION,
                    input,
                    decision);
        }
        if (decision.contextPresent() && !decision.tenantScopePresent()) {
            return result(
                    AiConsumerVerificationDecisionStatus.DECISION_BLOCKED,
                    AiConsumerVerificationDecisionReasonCodes.MISSING_TENANT_SCOPE,
                    input,
                    decision);
        }
        if (decision.verificationResultCheckAttempted()) {
            return result(
                    AiConsumerVerificationDecisionStatus.DECISION_REQUIRES_VERIFICATION_RESULT,
                    AiConsumerVerificationDecisionReasonCodes.DECISION_REQUIRES_VERIFICATION_RESULT,
                    input,
                    decision);
        }
        if (decision.evidenceCheckAttempted()) {
            return result(
                    AiConsumerVerificationDecisionStatus.DECISION_REQUIRES_VERIFIED_EVIDENCE,
                    AiConsumerVerificationDecisionReasonCodes.DECISION_REQUIRES_VERIFIED_EVIDENCE,
                    input,
                    decision);
        }
        if (decision.policyProviderCheckAttempted()) {
            return result(
                    AiConsumerVerificationDecisionStatus.DECISION_REQUIRES_REAL_POLICY_PROVIDER,
                    AiConsumerVerificationDecisionReasonCodes.DECISION_REQUIRES_REAL_POLICY_PROVIDER,
                    input,
                    decision);
        }
        if (decision.authorizationCheckAttempted()) {
            return result(
                    AiConsumerVerificationDecisionStatus.DECISION_REQUIRES_REAL_AUTHORIZATION,
                    AiConsumerVerificationDecisionReasonCodes.DECISION_REQUIRES_REAL_AUTHORIZATION,
                    input,
                    decision);
        }
        if (decision.humanReviewCheckAttempted()) {
            return result(
                    AiConsumerVerificationDecisionStatus.DECISION_REQUIRES_HUMAN_REVIEW,
                    AiConsumerVerificationDecisionReasonCodes.DECISION_REQUIRES_HUMAN_REVIEW,
                    input,
                    decision);
        }
        return result(
                AiConsumerVerificationDecisionStatus.VERIFICATION_DECISION_NOT_AVAILABLE,
                AiConsumerVerificationDecisionReasonCodes.VERIFICATION_DECISION_NOT_AVAILABLE,
                input,
                decision);
    }

    private static boolean untrustedAssertion(
            AiConsumerVerificationDecisionInput input, VerificationDecisionContext decision) {
        return input.clinicalDataAccessGranted()
                || input.clinicalDataAccessAllowed()
                || input.clinicalDataAccessEnforced()
                || input.executionVerified()
                || decision.decisionAvailableClaim()
                || decision.decisionEvaluatedClaim()
                || decision.verificationInputAcceptedClaim()
                || decision.verificationEvidenceAcceptedClaim()
                || decision.verificationDecisionAvailableClaim()
                || decision.verificationDecisionProviderConfiguredClaim()
                || decision.verificationApprovedClaim()
                || decision.clinicalDataAccessGrantedClaim()
                || decision.clinicalDataAccessAllowedClaim()
                || decision.clinicalDataAccessEnforcedClaim()
                || decision.executionVerifiedClaim();
    }

    private static AiConsumerVerificationDecisionResult missingVerification() {
        return result(
                AiConsumerVerificationDecisionStatus.DECISION_INPUT_NOT_AVAILABLE,
                AiConsumerVerificationDecisionReasonCodes.MISSING_VERIFICATION_RESULT,
                null,
                VerificationDecisionContext.laboratory());
    }

    private static AiConsumerVerificationDecisionResult result(
            AiConsumerVerificationDecisionStatus status,
            String reason,
            AiConsumerVerificationDecisionInput input,
            VerificationDecisionContext decision) {
        boolean synthetic = decision.verificationResultCheckAttempted()
                || decision.evidenceCheckAttempted()
                || decision.policyProviderCheckAttempted()
                || decision.authorizationCheckAttempted()
                || decision.humanReviewCheckAttempted();
        return AiConsumerVerificationDecisionResult.denied(
                status,
                reason,
                input != null && input.verificationResultPresent(),
                synthetic
                        ? VerificationDecisionContext.SOURCE_SYNTHETIC_DECISION
                        : VerificationDecisionContext.SOURCE_LABORATORY);
    }
}

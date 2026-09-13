package lab.healthcare.fhir.aiconsumerenforcementverification;

import lab.healthcare.fhir.aiconsumerenforcementexecution.AiConsumerClinicalDataEnforcementExecutionResult;

/**
 * Deny-by-default clinical data-access enforcement-execution
 * verification boundary. Claimed execution is not verified evidence.
 * Task 071 never reads FHIR.
 */
public final class AiConsumerClinicalDataEnforcementExecutionVerificationBoundary {

    private AiConsumerClinicalDataEnforcementExecutionVerificationBoundary() {
    }

    public static AiConsumerClinicalDataEnforcementExecutionVerificationResult evaluate(
            AiConsumerClinicalDataEnforcementExecutionResult execution) {
        if (execution == null) {
            return missingExecution();
        }
        return evaluate(AiConsumerClinicalDataEnforcementExecutionVerificationInput.from(execution));
    }

    public static AiConsumerClinicalDataEnforcementExecutionVerificationResult evaluate(
            AiConsumerClinicalDataEnforcementExecutionResult execution,
            ClinicalDataEnforcementExecutionVerificationContext verification) {
        if (execution == null) {
            return missingExecution();
        }
        return evaluate(AiConsumerClinicalDataEnforcementExecutionVerificationInput.of(execution, verification));
    }

    public static AiConsumerClinicalDataEnforcementExecutionVerificationResult evaluate(
            AiConsumerClinicalDataEnforcementExecutionVerificationInput input) {
        if (input == null || !input.executionResultPresent()) {
            return missingExecution();
        }
        ClinicalDataEnforcementExecutionVerificationContext verification =
                input.verification() == null
                        ? ClinicalDataEnforcementExecutionVerificationContext.laboratory()
                        : input.verification();
        if (untrustedAssertion(input, verification)) {
            return result(
                    AiConsumerClinicalDataEnforcementExecutionVerificationStatus.VERIFICATION_BLOCKED,
                    AiConsumerClinicalDataEnforcementExecutionVerificationReasonCodes
                            .UNTRUSTED_VERIFICATION_ASSERTION,
                    input,
                    verification);
        }
        if (verification.contextPresent() && !verification.tenantScopePresent()) {
            return result(
                    AiConsumerClinicalDataEnforcementExecutionVerificationStatus.VERIFICATION_BLOCKED,
                    AiConsumerClinicalDataEnforcementExecutionVerificationReasonCodes.MISSING_TENANT_SCOPE,
                    input,
                    verification);
        }
        if (verification.executionResultCheckAttempted()) {
            return result(
                    AiConsumerClinicalDataEnforcementExecutionVerificationStatus
                            .VERIFICATION_REQUIRES_EXECUTION_RESULT,
                    AiConsumerClinicalDataEnforcementExecutionVerificationReasonCodes
                            .VERIFICATION_REQUIRES_EXECUTION_RESULT,
                    input,
                    verification);
        }
        if (verification.evidenceCheckAttempted()) {
            return result(
                    AiConsumerClinicalDataEnforcementExecutionVerificationStatus.VERIFICATION_REQUIRES_EVIDENCE,
                    AiConsumerClinicalDataEnforcementExecutionVerificationReasonCodes.VERIFICATION_REQUIRES_EVIDENCE,
                    input,
                    verification);
        }
        if (verification.providerCheckAttempted()) {
            return result(
                    AiConsumerClinicalDataEnforcementExecutionVerificationStatus.VERIFICATION_REQUIRES_REAL_PROVIDER,
                    AiConsumerClinicalDataEnforcementExecutionVerificationReasonCodes
                            .VERIFICATION_REQUIRES_REAL_PROVIDER,
                    input,
                    verification);
        }
        if (verification.humanReviewCheckAttempted()) {
            return result(
                    AiConsumerClinicalDataEnforcementExecutionVerificationStatus.VERIFICATION_REQUIRES_HUMAN_REVIEW,
                    AiConsumerClinicalDataEnforcementExecutionVerificationReasonCodes
                            .VERIFICATION_REQUIRES_HUMAN_REVIEW,
                    input,
                    verification);
        }
        return result(
                AiConsumerClinicalDataEnforcementExecutionVerificationStatus.NOT_VERIFIED_FOR_CLINICAL_DATA_ACCESS,
                AiConsumerClinicalDataEnforcementExecutionVerificationReasonCodes.EXECUTION_NOT_VERIFIED,
                input,
                verification);
    }

    private static boolean untrustedAssertion(
            AiConsumerClinicalDataEnforcementExecutionVerificationInput input,
            ClinicalDataEnforcementExecutionVerificationContext verification) {
        return input.clinicalDataAccessGranted()
                || input.clinicalDataAccessAllowed()
                || input.clinicalDataAccessEnforced()
                || input.enforcementExecutionPerformed()
                || verification.verificationDecisionAvailableClaim()
                || verification.verificationDecisionEvaluatedClaim()
                || verification.executionEvidenceAvailableClaim()
                || verification.executionEvidenceEvaluatedClaim()
                || verification.executionVerificationAvailableClaim()
                || verification.executionVerificationProviderConfiguredClaim()
                || verification.executionVerifiedClaim()
                || verification.clinicalDataAccessGrantedClaim()
                || verification.clinicalDataAccessAllowedClaim()
                || verification.clinicalDataAccessEnforcedClaim()
                || verification.enforcementExecutionPerformedClaim();
    }

    private static AiConsumerClinicalDataEnforcementExecutionVerificationResult missingExecution() {
        return result(
                AiConsumerClinicalDataEnforcementExecutionVerificationStatus.VERIFICATION_INPUT_NOT_AVAILABLE,
                AiConsumerClinicalDataEnforcementExecutionVerificationReasonCodes.MISSING_EXECUTION_RESULT,
                null,
                ClinicalDataEnforcementExecutionVerificationContext.laboratory());
    }

    private static AiConsumerClinicalDataEnforcementExecutionVerificationResult result(
            AiConsumerClinicalDataEnforcementExecutionVerificationStatus status,
            String reason,
            AiConsumerClinicalDataEnforcementExecutionVerificationInput input,
            ClinicalDataEnforcementExecutionVerificationContext verification) {
        boolean synthetic = verification.executionResultCheckAttempted()
                || verification.evidenceCheckAttempted()
                || verification.providerCheckAttempted()
                || verification.humanReviewCheckAttempted();
        return AiConsumerClinicalDataEnforcementExecutionVerificationResult.denied(
                status,
                reason,
                input != null && input.executionResultPresent(),
                synthetic
                        ? ClinicalDataEnforcementExecutionVerificationContext.SOURCE_SYNTHETIC_VERIFICATION
                        : ClinicalDataEnforcementExecutionVerificationContext.SOURCE_LABORATORY);
    }
}

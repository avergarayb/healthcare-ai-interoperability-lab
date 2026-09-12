package lab.healthcare.fhir.aiconsumerenforcementexecution;

import lab.healthcare.fhir.aiconsumerenforcement.AiConsumerClinicalDataEnforcementResult;

/**
 * Deny-by-default clinical data-access enforcement-execution boundary.
 * An enforcement decision is not execution. Task 070 never reads FHIR.
 */
public final class AiConsumerClinicalDataEnforcementExecutionBoundary {

    private AiConsumerClinicalDataEnforcementExecutionBoundary() {
    }

    public static AiConsumerClinicalDataEnforcementExecutionResult evaluate(
            AiConsumerClinicalDataEnforcementResult enforcement) {
        if (enforcement == null) {
            return missingEnforcement();
        }
        return evaluate(AiConsumerClinicalDataEnforcementExecutionInput.from(enforcement));
    }

    public static AiConsumerClinicalDataEnforcementExecutionResult evaluate(
            AiConsumerClinicalDataEnforcementResult enforcement,
            ClinicalDataEnforcementExecutionContext execution) {
        if (enforcement == null) {
            return missingEnforcement();
        }
        return evaluate(AiConsumerClinicalDataEnforcementExecutionInput.of(enforcement, execution));
    }

    public static AiConsumerClinicalDataEnforcementExecutionResult evaluate(
            AiConsumerClinicalDataEnforcementExecutionInput input) {
        if (input == null || !input.enforcementResultPresent()) {
            return missingEnforcement();
        }
        ClinicalDataEnforcementExecutionContext execution =
                input.execution() == null
                        ? ClinicalDataEnforcementExecutionContext.laboratory()
                        : input.execution();
        if (untrustedAssertion(input, execution)) {
            return result(
                    AiConsumerClinicalDataEnforcementExecutionStatus.EXECUTION_BLOCKED,
                    AiConsumerClinicalDataEnforcementExecutionReasonCodes.UNTRUSTED_EXECUTION_ASSERTION,
                    input,
                    execution);
        }
        if (execution.contextPresent() && !execution.tenantScopePresent()) {
            return result(
                    AiConsumerClinicalDataEnforcementExecutionStatus.EXECUTION_BLOCKED,
                    AiConsumerClinicalDataEnforcementExecutionReasonCodes.MISSING_TENANT_SCOPE,
                    input,
                    execution);
        }
        if (execution.enforcementDecisionCheckAttempted()) {
            return result(
                    AiConsumerClinicalDataEnforcementExecutionStatus.EXECUTION_REQUIRES_ENFORCEMENT_DECISION,
                    AiConsumerClinicalDataEnforcementExecutionReasonCodes.EXECUTION_REQUIRES_ENFORCEMENT_DECISION,
                    input,
                    execution);
        }
        if (execution.authorizationEvaluationAttempted()) {
            return result(
                    AiConsumerClinicalDataEnforcementExecutionStatus.EXECUTION_REQUIRES_REAL_AUTHORIZATION,
                    AiConsumerClinicalDataEnforcementExecutionReasonCodes.EXECUTION_REQUIRES_REAL_AUTHORIZATION,
                    input,
                    execution);
        }
        if (execution.humanReviewCheckAttempted()) {
            return result(
                    AiConsumerClinicalDataEnforcementExecutionStatus.EXECUTION_REQUIRES_HUMAN_REVIEW,
                    AiConsumerClinicalDataEnforcementExecutionReasonCodes.EXECUTION_REQUIRES_HUMAN_REVIEW,
                    input,
                    execution);
        }
        return result(
                AiConsumerClinicalDataEnforcementExecutionStatus.NOT_EXECUTED_FOR_CLINICAL_DATA_ACCESS,
                AiConsumerClinicalDataEnforcementExecutionReasonCodes.ENFORCEMENT_NOT_EXECUTED,
                input,
                execution);
    }

    private static boolean untrustedAssertion(
            AiConsumerClinicalDataEnforcementExecutionInput input,
            ClinicalDataEnforcementExecutionContext execution) {
        return input.clinicalDataAccessGranted()
                || input.clinicalDataAccessAllowed()
                || input.clinicalDataAccessEnforced()
                || execution.executionDecisionAvailableClaim()
                || execution.executionDecisionEvaluatedClaim()
                || execution.enforcementExecutionAvailableClaim()
                || execution.enforcementExecutionProviderConfiguredClaim()
                || execution.enforcementExecutionPerformedClaim()
                || execution.clinicalDataAccessGrantedClaim()
                || execution.clinicalDataAccessAllowedClaim()
                || execution.clinicalDataAccessEnforcedClaim();
    }

    private static AiConsumerClinicalDataEnforcementExecutionResult missingEnforcement() {
        return result(
                AiConsumerClinicalDataEnforcementExecutionStatus.EXECUTION_INPUT_NOT_AVAILABLE,
                AiConsumerClinicalDataEnforcementExecutionReasonCodes.MISSING_ENFORCEMENT_RESULT,
                null,
                ClinicalDataEnforcementExecutionContext.laboratory());
    }

    private static AiConsumerClinicalDataEnforcementExecutionResult result(
            AiConsumerClinicalDataEnforcementExecutionStatus status,
            String reason,
            AiConsumerClinicalDataEnforcementExecutionInput input,
            ClinicalDataEnforcementExecutionContext execution) {
        boolean synthetic = execution.enforcementDecisionCheckAttempted()
                || execution.authorizationEvaluationAttempted()
                || execution.humanReviewCheckAttempted();
        return AiConsumerClinicalDataEnforcementExecutionResult.denied(
                status,
                reason,
                input != null && input.enforcementResultPresent(),
                synthetic
                        ? ClinicalDataEnforcementExecutionContext.SOURCE_SYNTHETIC_EXECUTION
                        : ClinicalDataEnforcementExecutionContext.SOURCE_LABORATORY);
    }
}

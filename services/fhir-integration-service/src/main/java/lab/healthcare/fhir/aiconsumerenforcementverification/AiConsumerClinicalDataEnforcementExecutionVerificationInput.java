package lab.healthcare.fhir.aiconsumerenforcementverification;

import lab.healthcare.fhir.aiconsumerenforcementexecution.AiConsumerClinicalDataEnforcementExecutionResult;

/**
 * Verification input copied from an execution result plus a synthetic
 * context. Unlike the 070 result, this record may hold
 * {@code enforcementExecutionPerformed=true} so the boundary can detect
 * that flag instead of treating it as verified evidence.
 */
public record AiConsumerClinicalDataEnforcementExecutionVerificationInput(
        boolean executionResultPresent,
        boolean enforcementExecutionPerformed,
        boolean executionDecisionAvailable,
        boolean clinicalDataAccessGranted,
        boolean clinicalDataAccessAllowed,
        boolean clinicalDataAccessEnforced,
        boolean requiresHumanReview,
        ClinicalDataEnforcementExecutionVerificationContext verification) {

    public static AiConsumerClinicalDataEnforcementExecutionVerificationInput from(
            AiConsumerClinicalDataEnforcementExecutionResult execution) {
        if (execution == null) {
            return null;
        }
        return new AiConsumerClinicalDataEnforcementExecutionVerificationInput(
                true,
                execution.enforcementExecutionPerformed(),
                execution.executionDecisionAvailable(),
                execution.clinicalDataAccessGranted(),
                execution.clinicalDataAccessAllowed(),
                execution.clinicalDataAccessEnforced(),
                execution.requiresHumanReview(),
                ClinicalDataEnforcementExecutionVerificationContext.laboratory());
    }

    public static AiConsumerClinicalDataEnforcementExecutionVerificationInput of(
            AiConsumerClinicalDataEnforcementExecutionResult execution,
            ClinicalDataEnforcementExecutionVerificationContext verification) {
        if (execution == null) {
            return null;
        }
        return new AiConsumerClinicalDataEnforcementExecutionVerificationInput(
                true,
                execution.enforcementExecutionPerformed(),
                execution.executionDecisionAvailable(),
                execution.clinicalDataAccessGranted(),
                execution.clinicalDataAccessAllowed(),
                execution.clinicalDataAccessEnforced(),
                execution.requiresHumanReview(),
                verification == null
                        ? ClinicalDataEnforcementExecutionVerificationContext.laboratory()
                        : verification);
    }

    public AiConsumerClinicalDataEnforcementExecutionVerificationInput withEnforcementExecutionPerformed(
            boolean value) {
        return new AiConsumerClinicalDataEnforcementExecutionVerificationInput(
                executionResultPresent,
                value,
                executionDecisionAvailable,
                clinicalDataAccessGranted,
                clinicalDataAccessAllowed,
                clinicalDataAccessEnforced,
                requiresHumanReview,
                verification);
    }

    public AiConsumerClinicalDataEnforcementExecutionVerificationInput withClinicalDataAccessGranted(boolean value) {
        return new AiConsumerClinicalDataEnforcementExecutionVerificationInput(
                executionResultPresent,
                enforcementExecutionPerformed,
                executionDecisionAvailable,
                value,
                clinicalDataAccessAllowed,
                clinicalDataAccessEnforced,
                requiresHumanReview,
                verification);
    }
}

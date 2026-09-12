package lab.healthcare.fhir.aiconsumerenforcementexecution;

import lab.healthcare.fhir.aiconsumerenforcement.AiConsumerClinicalDataEnforcementResult;

/**
 * Enforcement-execution input copied from an enforcement result plus a
 * synthetic context. Unlike the 069 result, this record may hold
 * {@code clinicalDataAccessGranted=true} so the boundary can detect
 * that flag instead of silently accepting it.
 */
public record AiConsumerClinicalDataEnforcementExecutionInput(
        boolean enforcementResultPresent,
        boolean enforcementDecisionAvailable,
        boolean enforcementDecisionEvaluated,
        boolean clinicalDataAccessGranted,
        boolean clinicalDataAccessAllowed,
        boolean clinicalDataAccessEnforced,
        boolean realAuthorizationRequired,
        boolean requiresHumanReview,
        ClinicalDataEnforcementExecutionContext execution) {

    public static AiConsumerClinicalDataEnforcementExecutionInput from(
            AiConsumerClinicalDataEnforcementResult enforcement) {
        if (enforcement == null) {
            return null;
        }
        return new AiConsumerClinicalDataEnforcementExecutionInput(
                true,
                enforcement.enforcementDecisionAvailable(),
                enforcement.enforcementDecisionEvaluated(),
                enforcement.clinicalDataAccessGranted(),
                enforcement.clinicalDataAccessAllowed(),
                enforcement.clinicalDataAccessEnforced(),
                enforcement.realAuthorizationRequired(),
                enforcement.requiresHumanReview(),
                ClinicalDataEnforcementExecutionContext.laboratory());
    }

    public static AiConsumerClinicalDataEnforcementExecutionInput of(
            AiConsumerClinicalDataEnforcementResult enforcement,
            ClinicalDataEnforcementExecutionContext execution) {
        if (enforcement == null) {
            return null;
        }
        return new AiConsumerClinicalDataEnforcementExecutionInput(
                true,
                enforcement.enforcementDecisionAvailable(),
                enforcement.enforcementDecisionEvaluated(),
                enforcement.clinicalDataAccessGranted(),
                enforcement.clinicalDataAccessAllowed(),
                enforcement.clinicalDataAccessEnforced(),
                enforcement.realAuthorizationRequired(),
                enforcement.requiresHumanReview(),
                execution == null ? ClinicalDataEnforcementExecutionContext.laboratory() : execution);
    }

    public AiConsumerClinicalDataEnforcementExecutionInput withClinicalDataAccessGranted(boolean value) {
        return new AiConsumerClinicalDataEnforcementExecutionInput(
                enforcementResultPresent,
                enforcementDecisionAvailable,
                enforcementDecisionEvaluated,
                value,
                clinicalDataAccessAllowed,
                clinicalDataAccessEnforced,
                realAuthorizationRequired,
                requiresHumanReview,
                execution);
    }
}

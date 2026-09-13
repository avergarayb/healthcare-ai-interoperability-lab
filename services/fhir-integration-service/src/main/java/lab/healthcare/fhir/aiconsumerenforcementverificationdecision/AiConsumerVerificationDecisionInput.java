package lab.healthcare.fhir.aiconsumerenforcementverificationdecision;

import lab.healthcare.fhir.aiconsumerenforcementverification.AiConsumerClinicalDataEnforcementExecutionVerificationResult;

/**
 * Decision input copied from a verification result plus a synthetic
 * context. Unlike the 071 result, this record may hold
 * {@code executionVerified=true} so the boundary can detect that flag
 * instead of treating it as an approval.
 */
public record AiConsumerVerificationDecisionInput(
        boolean verificationResultPresent,
        boolean executionVerified,
        boolean verificationDecisionAvailable,
        boolean clinicalDataAccessGranted,
        boolean clinicalDataAccessAllowed,
        boolean clinicalDataAccessEnforced,
        boolean requiresHumanReview,
        VerificationDecisionContext decision) {

    public static AiConsumerVerificationDecisionInput from(
            AiConsumerClinicalDataEnforcementExecutionVerificationResult verification) {
        if (verification == null) {
            return null;
        }
        return new AiConsumerVerificationDecisionInput(
                true,
                verification.executionVerified(),
                verification.verificationDecisionAvailable(),
                verification.clinicalDataAccessGranted(),
                verification.clinicalDataAccessAllowed(),
                verification.clinicalDataAccessEnforced(),
                verification.requiresHumanReview(),
                VerificationDecisionContext.laboratory());
    }

    public static AiConsumerVerificationDecisionInput of(
            AiConsumerClinicalDataEnforcementExecutionVerificationResult verification,
            VerificationDecisionContext decision) {
        if (verification == null) {
            return null;
        }
        return new AiConsumerVerificationDecisionInput(
                true,
                verification.executionVerified(),
                verification.verificationDecisionAvailable(),
                verification.clinicalDataAccessGranted(),
                verification.clinicalDataAccessAllowed(),
                verification.clinicalDataAccessEnforced(),
                verification.requiresHumanReview(),
                decision == null ? VerificationDecisionContext.laboratory() : decision);
    }

    public AiConsumerVerificationDecisionInput withExecutionVerified(boolean value) {
        return new AiConsumerVerificationDecisionInput(
                verificationResultPresent,
                value,
                verificationDecisionAvailable,
                clinicalDataAccessGranted,
                clinicalDataAccessAllowed,
                clinicalDataAccessEnforced,
                requiresHumanReview,
                decision);
    }

    public AiConsumerVerificationDecisionInput withClinicalDataAccessGranted(boolean value) {
        return new AiConsumerVerificationDecisionInput(
                verificationResultPresent,
                executionVerified,
                verificationDecisionAvailable,
                value,
                clinicalDataAccessAllowed,
                clinicalDataAccessEnforced,
                requiresHumanReview,
                decision);
    }
}

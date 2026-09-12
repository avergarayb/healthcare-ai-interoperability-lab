package lab.healthcare.fhir.aiconsumerenforcementexecution;

/**
 * Synthetic, untrusted enforcement-execution metadata. A claimed
 * execution is not a grant and is not a FHIR read.
 */
public record ClinicalDataEnforcementExecutionContext(
        boolean contextPresent,
        boolean tenantScopePresent,
        boolean enforcementDecisionCheckAttempted,
        boolean authorizationEvaluationAttempted,
        boolean humanReviewCheckAttempted,
        boolean executionDecisionAvailableClaim,
        boolean executionDecisionEvaluatedClaim,
        boolean enforcementExecutionAvailableClaim,
        boolean enforcementExecutionProviderConfiguredClaim,
        boolean enforcementExecutionPerformedClaim,
        boolean clinicalDataAccessGrantedClaim,
        boolean clinicalDataAccessAllowedClaim,
        boolean clinicalDataAccessEnforcedClaim) {

    public static final String SOURCE_LABORATORY = "LABORATORY";
    public static final String SOURCE_SYNTHETIC_EXECUTION = "SYNTHETIC_EXECUTION";

    public static ClinicalDataEnforcementExecutionContext laboratory() {
        return new ClinicalDataEnforcementExecutionContext(
                true,
                true,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false);
    }

    public ClinicalDataEnforcementExecutionContext withTenantScopePresent(boolean value) {
        return copy(
                contextPresent,
                value,
                enforcementDecisionCheckAttempted,
                authorizationEvaluationAttempted,
                humanReviewCheckAttempted,
                executionDecisionAvailableClaim,
                executionDecisionEvaluatedClaim,
                enforcementExecutionAvailableClaim,
                enforcementExecutionProviderConfiguredClaim,
                enforcementExecutionPerformedClaim,
                clinicalDataAccessGrantedClaim,
                clinicalDataAccessAllowedClaim,
                clinicalDataAccessEnforcedClaim);
    }

    public ClinicalDataEnforcementExecutionContext withEnforcementDecisionCheckAttempted(boolean value) {
        return copy(
                contextPresent,
                tenantScopePresent,
                value,
                authorizationEvaluationAttempted,
                humanReviewCheckAttempted,
                executionDecisionAvailableClaim,
                executionDecisionEvaluatedClaim,
                enforcementExecutionAvailableClaim,
                enforcementExecutionProviderConfiguredClaim,
                enforcementExecutionPerformedClaim,
                clinicalDataAccessGrantedClaim,
                clinicalDataAccessAllowedClaim,
                clinicalDataAccessEnforcedClaim);
    }

    public ClinicalDataEnforcementExecutionContext withAuthorizationEvaluationAttempted(boolean value) {
        return copy(
                contextPresent,
                tenantScopePresent,
                enforcementDecisionCheckAttempted,
                value,
                humanReviewCheckAttempted,
                executionDecisionAvailableClaim,
                executionDecisionEvaluatedClaim,
                enforcementExecutionAvailableClaim,
                enforcementExecutionProviderConfiguredClaim,
                enforcementExecutionPerformedClaim,
                clinicalDataAccessGrantedClaim,
                clinicalDataAccessAllowedClaim,
                clinicalDataAccessEnforcedClaim);
    }

    public ClinicalDataEnforcementExecutionContext withHumanReviewCheckAttempted(boolean value) {
        return copy(
                contextPresent,
                tenantScopePresent,
                enforcementDecisionCheckAttempted,
                authorizationEvaluationAttempted,
                value,
                executionDecisionAvailableClaim,
                executionDecisionEvaluatedClaim,
                enforcementExecutionAvailableClaim,
                enforcementExecutionProviderConfiguredClaim,
                enforcementExecutionPerformedClaim,
                clinicalDataAccessGrantedClaim,
                clinicalDataAccessAllowedClaim,
                clinicalDataAccessEnforcedClaim);
    }

    public ClinicalDataEnforcementExecutionContext withPositiveClaims() {
        return copy(
                contextPresent,
                tenantScopePresent,
                enforcementDecisionCheckAttempted,
                authorizationEvaluationAttempted,
                humanReviewCheckAttempted,
                true,
                true,
                true,
                true,
                true,
                true,
                true,
                true);
    }

    private ClinicalDataEnforcementExecutionContext copy(
            boolean contextPresent,
            boolean tenantScopePresent,
            boolean enforcementDecisionCheckAttempted,
            boolean authorizationEvaluationAttempted,
            boolean humanReviewCheckAttempted,
            boolean executionDecisionAvailableClaim,
            boolean executionDecisionEvaluatedClaim,
            boolean enforcementExecutionAvailableClaim,
            boolean enforcementExecutionProviderConfiguredClaim,
            boolean enforcementExecutionPerformedClaim,
            boolean clinicalDataAccessGrantedClaim,
            boolean clinicalDataAccessAllowedClaim,
            boolean clinicalDataAccessEnforcedClaim) {
        return new ClinicalDataEnforcementExecutionContext(
                contextPresent,
                tenantScopePresent,
                enforcementDecisionCheckAttempted,
                authorizationEvaluationAttempted,
                humanReviewCheckAttempted,
                executionDecisionAvailableClaim,
                executionDecisionEvaluatedClaim,
                enforcementExecutionAvailableClaim,
                enforcementExecutionProviderConfiguredClaim,
                enforcementExecutionPerformedClaim,
                clinicalDataAccessGrantedClaim,
                clinicalDataAccessAllowedClaim,
                clinicalDataAccessEnforcedClaim);
    }
}

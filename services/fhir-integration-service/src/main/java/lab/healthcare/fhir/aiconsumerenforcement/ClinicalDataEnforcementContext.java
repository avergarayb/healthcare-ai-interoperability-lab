package lab.healthcare.fhir.aiconsumerenforcement;

/**
 * Synthetic, untrusted enforcement metadata. A claimed decision is not
 * evaluation and is not a grant. Never includes Patient identifiers,
 * tokens, or FHIR JSON.
 */
public record ClinicalDataEnforcementContext(
        boolean contextPresent,
        boolean tenantScopePresent,
        boolean requestReferencePresent,
        boolean authorizationEvaluationAttempted,
        boolean authorizationDecisionReferencePresent,
        boolean enforcementDecisionAvailableClaim,
        boolean enforcementDecisionEvaluatedClaim,
        boolean clinicalDataAccessGrantedClaim,
        boolean clinicalDataAccessAllowedClaim,
        boolean clinicalDataAccessEnforcedClaim,
        boolean clinicalDataAccessEnforcementAvailableClaim,
        boolean clinicalDataAccessEnforcementProviderConfigured,
        boolean clinicalDataAccessEnforcementExecutedClaim) {

    public static final String SOURCE_LABORATORY = "LABORATORY";
    public static final String SOURCE_SYNTHETIC_ENFORCEMENT = "SYNTHETIC_ENFORCEMENT";

    public static ClinicalDataEnforcementContext laboratory() {
        return new ClinicalDataEnforcementContext(
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

    public ClinicalDataEnforcementContext withTenantScopePresent(boolean value) {
        return new ClinicalDataEnforcementContext(
                contextPresent,
                value,
                requestReferencePresent,
                authorizationEvaluationAttempted,
                authorizationDecisionReferencePresent,
                enforcementDecisionAvailableClaim,
                enforcementDecisionEvaluatedClaim,
                clinicalDataAccessGrantedClaim,
                clinicalDataAccessAllowedClaim,
                clinicalDataAccessEnforcedClaim,
                clinicalDataAccessEnforcementAvailableClaim,
                clinicalDataAccessEnforcementProviderConfigured,
                clinicalDataAccessEnforcementExecutedClaim);
    }

    public ClinicalDataEnforcementContext withRequestReferencePresent(boolean value) {
        return new ClinicalDataEnforcementContext(
                contextPresent,
                tenantScopePresent,
                value,
                authorizationEvaluationAttempted,
                authorizationDecisionReferencePresent,
                enforcementDecisionAvailableClaim,
                enforcementDecisionEvaluatedClaim,
                clinicalDataAccessGrantedClaim,
                clinicalDataAccessAllowedClaim,
                clinicalDataAccessEnforcedClaim,
                clinicalDataAccessEnforcementAvailableClaim,
                clinicalDataAccessEnforcementProviderConfigured,
                clinicalDataAccessEnforcementExecutedClaim);
    }

    public ClinicalDataEnforcementContext withAuthorizationEvaluationAttempted(boolean value) {
        return new ClinicalDataEnforcementContext(
                contextPresent,
                tenantScopePresent,
                requestReferencePresent,
                value,
                authorizationDecisionReferencePresent,
                enforcementDecisionAvailableClaim,
                enforcementDecisionEvaluatedClaim,
                clinicalDataAccessGrantedClaim,
                clinicalDataAccessAllowedClaim,
                clinicalDataAccessEnforcedClaim,
                clinicalDataAccessEnforcementAvailableClaim,
                clinicalDataAccessEnforcementProviderConfigured,
                clinicalDataAccessEnforcementExecutedClaim);
    }

    public ClinicalDataEnforcementContext withPositiveClaims() {
        return new ClinicalDataEnforcementContext(
                contextPresent,
                tenantScopePresent,
                requestReferencePresent,
                authorizationEvaluationAttempted,
                authorizationDecisionReferencePresent,
                true,
                true,
                true,
                true,
                true,
                true,
                true,
                true);
    }
}

package lab.healthcare.fhir.aiconsumerenforcementverificationdecision;

/**
 * Synthetic, untrusted verification-decision metadata. A claimed
 * decision is not approval and is not a FHIR read.
 */
public record VerificationDecisionContext(
        boolean contextPresent,
        boolean tenantScopePresent,
        boolean verificationResultCheckAttempted,
        boolean evidenceCheckAttempted,
        boolean policyProviderCheckAttempted,
        boolean authorizationCheckAttempted,
        boolean humanReviewCheckAttempted,
        boolean decisionAvailableClaim,
        boolean decisionEvaluatedClaim,
        boolean verificationInputAcceptedClaim,
        boolean verificationEvidenceAcceptedClaim,
        boolean verificationDecisionAvailableClaim,
        boolean verificationDecisionProviderConfiguredClaim,
        boolean verificationApprovedClaim,
        boolean clinicalDataAccessGrantedClaim,
        boolean clinicalDataAccessAllowedClaim,
        boolean clinicalDataAccessEnforcedClaim,
        boolean executionVerifiedClaim) {

    public static final String SOURCE_LABORATORY = "LABORATORY";
    public static final String SOURCE_SYNTHETIC_DECISION = "SYNTHETIC_DECISION";

    public static VerificationDecisionContext laboratory() {
        return new VerificationDecisionContext(
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
                false,
                false,
                false,
                false,
                false,
                false);
    }

    public VerificationDecisionContext withTenantScopePresent(boolean value) {
        return copy(contextPresent, value, verificationResultCheckAttempted, evidenceCheckAttempted,
                policyProviderCheckAttempted, authorizationCheckAttempted, humanReviewCheckAttempted,
                decisionAvailableClaim, decisionEvaluatedClaim, verificationInputAcceptedClaim,
                verificationEvidenceAcceptedClaim, verificationDecisionAvailableClaim,
                verificationDecisionProviderConfiguredClaim, verificationApprovedClaim,
                clinicalDataAccessGrantedClaim, clinicalDataAccessAllowedClaim,
                clinicalDataAccessEnforcedClaim, executionVerifiedClaim);
    }

    public VerificationDecisionContext withVerificationResultCheckAttempted(boolean value) {
        return copy(contextPresent, tenantScopePresent, value, evidenceCheckAttempted,
                policyProviderCheckAttempted, authorizationCheckAttempted, humanReviewCheckAttempted,
                decisionAvailableClaim, decisionEvaluatedClaim, verificationInputAcceptedClaim,
                verificationEvidenceAcceptedClaim, verificationDecisionAvailableClaim,
                verificationDecisionProviderConfiguredClaim, verificationApprovedClaim,
                clinicalDataAccessGrantedClaim, clinicalDataAccessAllowedClaim,
                clinicalDataAccessEnforcedClaim, executionVerifiedClaim);
    }

    public VerificationDecisionContext withEvidenceCheckAttempted(boolean value) {
        return copy(contextPresent, tenantScopePresent, verificationResultCheckAttempted, value,
                policyProviderCheckAttempted, authorizationCheckAttempted, humanReviewCheckAttempted,
                decisionAvailableClaim, decisionEvaluatedClaim, verificationInputAcceptedClaim,
                verificationEvidenceAcceptedClaim, verificationDecisionAvailableClaim,
                verificationDecisionProviderConfiguredClaim, verificationApprovedClaim,
                clinicalDataAccessGrantedClaim, clinicalDataAccessAllowedClaim,
                clinicalDataAccessEnforcedClaim, executionVerifiedClaim);
    }

    public VerificationDecisionContext withPolicyProviderCheckAttempted(boolean value) {
        return copy(contextPresent, tenantScopePresent, verificationResultCheckAttempted,
                evidenceCheckAttempted, value, authorizationCheckAttempted, humanReviewCheckAttempted,
                decisionAvailableClaim, decisionEvaluatedClaim, verificationInputAcceptedClaim,
                verificationEvidenceAcceptedClaim, verificationDecisionAvailableClaim,
                verificationDecisionProviderConfiguredClaim, verificationApprovedClaim,
                clinicalDataAccessGrantedClaim, clinicalDataAccessAllowedClaim,
                clinicalDataAccessEnforcedClaim, executionVerifiedClaim);
    }

    public VerificationDecisionContext withAuthorizationCheckAttempted(boolean value) {
        return copy(contextPresent, tenantScopePresent, verificationResultCheckAttempted,
                evidenceCheckAttempted, policyProviderCheckAttempted, value, humanReviewCheckAttempted,
                decisionAvailableClaim, decisionEvaluatedClaim, verificationInputAcceptedClaim,
                verificationEvidenceAcceptedClaim, verificationDecisionAvailableClaim,
                verificationDecisionProviderConfiguredClaim, verificationApprovedClaim,
                clinicalDataAccessGrantedClaim, clinicalDataAccessAllowedClaim,
                clinicalDataAccessEnforcedClaim, executionVerifiedClaim);
    }

    public VerificationDecisionContext withHumanReviewCheckAttempted(boolean value) {
        return copy(contextPresent, tenantScopePresent, verificationResultCheckAttempted,
                evidenceCheckAttempted, policyProviderCheckAttempted, authorizationCheckAttempted, value,
                decisionAvailableClaim, decisionEvaluatedClaim, verificationInputAcceptedClaim,
                verificationEvidenceAcceptedClaim, verificationDecisionAvailableClaim,
                verificationDecisionProviderConfiguredClaim, verificationApprovedClaim,
                clinicalDataAccessGrantedClaim, clinicalDataAccessAllowedClaim,
                clinicalDataAccessEnforcedClaim, executionVerifiedClaim);
    }

    public VerificationDecisionContext withPositiveClaims() {
        return copy(contextPresent, tenantScopePresent, verificationResultCheckAttempted,
                evidenceCheckAttempted, policyProviderCheckAttempted, authorizationCheckAttempted,
                humanReviewCheckAttempted, true, true, true, true, true, true, true, true, true, true, true);
    }

    private VerificationDecisionContext copy(
            boolean contextPresent,
            boolean tenantScopePresent,
            boolean verificationResultCheckAttempted,
            boolean evidenceCheckAttempted,
            boolean policyProviderCheckAttempted,
            boolean authorizationCheckAttempted,
            boolean humanReviewCheckAttempted,
            boolean decisionAvailableClaim,
            boolean decisionEvaluatedClaim,
            boolean verificationInputAcceptedClaim,
            boolean verificationEvidenceAcceptedClaim,
            boolean verificationDecisionAvailableClaim,
            boolean verificationDecisionProviderConfiguredClaim,
            boolean verificationApprovedClaim,
            boolean clinicalDataAccessGrantedClaim,
            boolean clinicalDataAccessAllowedClaim,
            boolean clinicalDataAccessEnforcedClaim,
            boolean executionVerifiedClaim) {
        return new VerificationDecisionContext(
                contextPresent,
                tenantScopePresent,
                verificationResultCheckAttempted,
                evidenceCheckAttempted,
                policyProviderCheckAttempted,
                authorizationCheckAttempted,
                humanReviewCheckAttempted,
                decisionAvailableClaim,
                decisionEvaluatedClaim,
                verificationInputAcceptedClaim,
                verificationEvidenceAcceptedClaim,
                verificationDecisionAvailableClaim,
                verificationDecisionProviderConfiguredClaim,
                verificationApprovedClaim,
                clinicalDataAccessGrantedClaim,
                clinicalDataAccessAllowedClaim,
                clinicalDataAccessEnforcedClaim,
                executionVerifiedClaim);
    }
}

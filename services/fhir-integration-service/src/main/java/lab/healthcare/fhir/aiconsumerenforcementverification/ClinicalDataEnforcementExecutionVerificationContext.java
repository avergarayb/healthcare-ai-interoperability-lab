package lab.healthcare.fhir.aiconsumerenforcementverification;

/**
 * Synthetic, untrusted verification metadata. A claimed verification
 * is not evidence and is not a FHIR read.
 */
public record ClinicalDataEnforcementExecutionVerificationContext(
        boolean contextPresent,
        boolean tenantScopePresent,
        boolean executionResultCheckAttempted,
        boolean evidenceCheckAttempted,
        boolean providerCheckAttempted,
        boolean humanReviewCheckAttempted,
        boolean verificationDecisionAvailableClaim,
        boolean verificationDecisionEvaluatedClaim,
        boolean executionEvidenceAvailableClaim,
        boolean executionEvidenceEvaluatedClaim,
        boolean executionVerificationAvailableClaim,
        boolean executionVerificationProviderConfiguredClaim,
        boolean executionVerifiedClaim,
        boolean clinicalDataAccessGrantedClaim,
        boolean clinicalDataAccessAllowedClaim,
        boolean clinicalDataAccessEnforcedClaim,
        boolean enforcementExecutionPerformedClaim) {

    public static final String SOURCE_LABORATORY = "LABORATORY";
    public static final String SOURCE_SYNTHETIC_VERIFICATION = "SYNTHETIC_VERIFICATION";

    public static ClinicalDataEnforcementExecutionVerificationContext laboratory() {
        return new ClinicalDataEnforcementExecutionVerificationContext(
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
                false);
    }

    public ClinicalDataEnforcementExecutionVerificationContext withTenantScopePresent(boolean value) {
        return copy(contextPresent, value, executionResultCheckAttempted, evidenceCheckAttempted,
                providerCheckAttempted, humanReviewCheckAttempted, verificationDecisionAvailableClaim,
                verificationDecisionEvaluatedClaim, executionEvidenceAvailableClaim, executionEvidenceEvaluatedClaim,
                executionVerificationAvailableClaim, executionVerificationProviderConfiguredClaim,
                executionVerifiedClaim, clinicalDataAccessGrantedClaim, clinicalDataAccessAllowedClaim,
                clinicalDataAccessEnforcedClaim, enforcementExecutionPerformedClaim);
    }

    public ClinicalDataEnforcementExecutionVerificationContext withExecutionResultCheckAttempted(boolean value) {
        return copy(contextPresent, tenantScopePresent, value, evidenceCheckAttempted,
                providerCheckAttempted, humanReviewCheckAttempted, verificationDecisionAvailableClaim,
                verificationDecisionEvaluatedClaim, executionEvidenceAvailableClaim, executionEvidenceEvaluatedClaim,
                executionVerificationAvailableClaim, executionVerificationProviderConfiguredClaim,
                executionVerifiedClaim, clinicalDataAccessGrantedClaim, clinicalDataAccessAllowedClaim,
                clinicalDataAccessEnforcedClaim, enforcementExecutionPerformedClaim);
    }

    public ClinicalDataEnforcementExecutionVerificationContext withEvidenceCheckAttempted(boolean value) {
        return copy(contextPresent, tenantScopePresent, executionResultCheckAttempted, value,
                providerCheckAttempted, humanReviewCheckAttempted, verificationDecisionAvailableClaim,
                verificationDecisionEvaluatedClaim, executionEvidenceAvailableClaim, executionEvidenceEvaluatedClaim,
                executionVerificationAvailableClaim, executionVerificationProviderConfiguredClaim,
                executionVerifiedClaim, clinicalDataAccessGrantedClaim, clinicalDataAccessAllowedClaim,
                clinicalDataAccessEnforcedClaim, enforcementExecutionPerformedClaim);
    }

    public ClinicalDataEnforcementExecutionVerificationContext withProviderCheckAttempted(boolean value) {
        return copy(contextPresent, tenantScopePresent, executionResultCheckAttempted, evidenceCheckAttempted,
                value, humanReviewCheckAttempted, verificationDecisionAvailableClaim,
                verificationDecisionEvaluatedClaim, executionEvidenceAvailableClaim, executionEvidenceEvaluatedClaim,
                executionVerificationAvailableClaim, executionVerificationProviderConfiguredClaim,
                executionVerifiedClaim, clinicalDataAccessGrantedClaim, clinicalDataAccessAllowedClaim,
                clinicalDataAccessEnforcedClaim, enforcementExecutionPerformedClaim);
    }

    public ClinicalDataEnforcementExecutionVerificationContext withHumanReviewCheckAttempted(boolean value) {
        return copy(contextPresent, tenantScopePresent, executionResultCheckAttempted, evidenceCheckAttempted,
                providerCheckAttempted, value, verificationDecisionAvailableClaim,
                verificationDecisionEvaluatedClaim, executionEvidenceAvailableClaim, executionEvidenceEvaluatedClaim,
                executionVerificationAvailableClaim, executionVerificationProviderConfiguredClaim,
                executionVerifiedClaim, clinicalDataAccessGrantedClaim, clinicalDataAccessAllowedClaim,
                clinicalDataAccessEnforcedClaim, enforcementExecutionPerformedClaim);
    }

    public ClinicalDataEnforcementExecutionVerificationContext withPositiveClaims() {
        return copy(contextPresent, tenantScopePresent, executionResultCheckAttempted, evidenceCheckAttempted,
                providerCheckAttempted, humanReviewCheckAttempted, true, true, true, true, true, true, true,
                true, true, true, true);
    }

    private ClinicalDataEnforcementExecutionVerificationContext copy(
            boolean contextPresent,
            boolean tenantScopePresent,
            boolean executionResultCheckAttempted,
            boolean evidenceCheckAttempted,
            boolean providerCheckAttempted,
            boolean humanReviewCheckAttempted,
            boolean verificationDecisionAvailableClaim,
            boolean verificationDecisionEvaluatedClaim,
            boolean executionEvidenceAvailableClaim,
            boolean executionEvidenceEvaluatedClaim,
            boolean executionVerificationAvailableClaim,
            boolean executionVerificationProviderConfiguredClaim,
            boolean executionVerifiedClaim,
            boolean clinicalDataAccessGrantedClaim,
            boolean clinicalDataAccessAllowedClaim,
            boolean clinicalDataAccessEnforcedClaim,
            boolean enforcementExecutionPerformedClaim) {
        return new ClinicalDataEnforcementExecutionVerificationContext(
                contextPresent,
                tenantScopePresent,
                executionResultCheckAttempted,
                evidenceCheckAttempted,
                providerCheckAttempted,
                humanReviewCheckAttempted,
                verificationDecisionAvailableClaim,
                verificationDecisionEvaluatedClaim,
                executionEvidenceAvailableClaim,
                executionEvidenceEvaluatedClaim,
                executionVerificationAvailableClaim,
                executionVerificationProviderConfiguredClaim,
                executionVerifiedClaim,
                clinicalDataAccessGrantedClaim,
                clinicalDataAccessAllowedClaim,
                clinicalDataAccessEnforcedClaim,
                enforcementExecutionPerformedClaim);
    }
}

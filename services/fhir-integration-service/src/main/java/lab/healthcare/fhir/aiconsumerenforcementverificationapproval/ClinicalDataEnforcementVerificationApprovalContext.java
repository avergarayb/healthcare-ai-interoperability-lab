package lab.healthcare.fhir.aiconsumerenforcementverificationapproval;

/**
 * Synthetic, untrusted verification-approval metadata. A claimed
 * approval is not a clinical grant and is not a FHIR read.
 */
public record ClinicalDataEnforcementVerificationApprovalContext(
        boolean contextPresent,
        boolean approvalDecisionDeclared,
        boolean approvalDecisionEvaluated,
        boolean approvalEvidenceReferencePresent,
        boolean approvalEvidenceSufficient,
        boolean approvalPolicyReferencePresent,
        boolean approvalPolicySatisfied,
        boolean approvalHumanReviewRequired,
        boolean approvalProviderConfigured,
        boolean approvalAvailable,
        boolean decisionAvailabilityCheckAttempted,
        boolean decisionEvaluatedCheckAttempted,
        boolean evidenceCheckAttempted) {

    public static final String SOURCE_LABORATORY = "LABORATORY";
    public static final String SOURCE_SYNTHETIC_APPROVAL = "SYNTHETIC_APPROVAL";

    public static ClinicalDataEnforcementVerificationApprovalContext laboratory() {
        return new ClinicalDataEnforcementVerificationApprovalContext(
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
                false);
    }

    public ClinicalDataEnforcementVerificationApprovalContext withApprovalHumanReviewRequired(boolean value) {
        return copy(
                contextPresent,
                approvalDecisionDeclared,
                approvalDecisionEvaluated,
                approvalEvidenceReferencePresent,
                approvalEvidenceSufficient,
                approvalPolicyReferencePresent,
                approvalPolicySatisfied,
                value,
                approvalProviderConfigured,
                approvalAvailable,
                decisionAvailabilityCheckAttempted,
                decisionEvaluatedCheckAttempted,
                evidenceCheckAttempted);
    }

    public ClinicalDataEnforcementVerificationApprovalContext withDecisionAvailabilityCheckAttempted(
            boolean value) {
        return copy(
                contextPresent,
                approvalDecisionDeclared,
                approvalDecisionEvaluated,
                approvalEvidenceReferencePresent,
                approvalEvidenceSufficient,
                approvalPolicyReferencePresent,
                approvalPolicySatisfied,
                approvalHumanReviewRequired,
                approvalProviderConfigured,
                approvalAvailable,
                value,
                decisionEvaluatedCheckAttempted,
                evidenceCheckAttempted);
    }

    public ClinicalDataEnforcementVerificationApprovalContext withDecisionEvaluatedCheckAttempted(boolean value) {
        return copy(
                contextPresent,
                approvalDecisionDeclared,
                approvalDecisionEvaluated,
                approvalEvidenceReferencePresent,
                approvalEvidenceSufficient,
                approvalPolicyReferencePresent,
                approvalPolicySatisfied,
                approvalHumanReviewRequired,
                approvalProviderConfigured,
                approvalAvailable,
                decisionAvailabilityCheckAttempted,
                value,
                evidenceCheckAttempted);
    }

    public ClinicalDataEnforcementVerificationApprovalContext withEvidenceCheckAttempted(boolean value) {
        return copy(
                contextPresent,
                approvalDecisionDeclared,
                approvalDecisionEvaluated,
                approvalEvidenceReferencePresent,
                approvalEvidenceSufficient,
                approvalPolicyReferencePresent,
                approvalPolicySatisfied,
                approvalHumanReviewRequired,
                approvalProviderConfigured,
                approvalAvailable,
                decisionAvailabilityCheckAttempted,
                decisionEvaluatedCheckAttempted,
                value);
    }

    public ClinicalDataEnforcementVerificationApprovalContext withEvidenceClaims() {
        return copy(
                contextPresent,
                approvalDecisionDeclared,
                approvalDecisionEvaluated,
                true,
                true,
                approvalPolicyReferencePresent,
                approvalPolicySatisfied,
                approvalHumanReviewRequired,
                approvalProviderConfigured,
                approvalAvailable,
                decisionAvailabilityCheckAttempted,
                decisionEvaluatedCheckAttempted,
                evidenceCheckAttempted);
    }

    public ClinicalDataEnforcementVerificationApprovalContext withPolicyClaims() {
        return copy(
                contextPresent,
                approvalDecisionDeclared,
                approvalDecisionEvaluated,
                approvalEvidenceReferencePresent,
                approvalEvidenceSufficient,
                true,
                true,
                approvalHumanReviewRequired,
                approvalProviderConfigured,
                approvalAvailable,
                decisionAvailabilityCheckAttempted,
                decisionEvaluatedCheckAttempted,
                evidenceCheckAttempted);
    }

    public ClinicalDataEnforcementVerificationApprovalContext withPositiveClaims() {
        return copy(contextPresent, true, true, true, true, true, true, approvalHumanReviewRequired, true, true,
                decisionAvailabilityCheckAttempted, decisionEvaluatedCheckAttempted, evidenceCheckAttempted);
    }

    public boolean hasUntrustedApprovalClaim() {
        return approvalDecisionDeclared
                || approvalDecisionEvaluated
                || approvalEvidenceReferencePresent
                || approvalEvidenceSufficient
                || approvalPolicyReferencePresent
                || approvalPolicySatisfied
                || approvalProviderConfigured
                || approvalAvailable;
    }

    private ClinicalDataEnforcementVerificationApprovalContext copy(
            boolean contextPresent,
            boolean approvalDecisionDeclared,
            boolean approvalDecisionEvaluated,
            boolean approvalEvidenceReferencePresent,
            boolean approvalEvidenceSufficient,
            boolean approvalPolicyReferencePresent,
            boolean approvalPolicySatisfied,
            boolean approvalHumanReviewRequired,
            boolean approvalProviderConfigured,
            boolean approvalAvailable,
            boolean decisionAvailabilityCheckAttempted,
            boolean decisionEvaluatedCheckAttempted,
            boolean evidenceCheckAttempted) {
        return new ClinicalDataEnforcementVerificationApprovalContext(
                contextPresent,
                approvalDecisionDeclared,
                approvalDecisionEvaluated,
                approvalEvidenceReferencePresent,
                approvalEvidenceSufficient,
                approvalPolicyReferencePresent,
                approvalPolicySatisfied,
                approvalHumanReviewRequired,
                approvalProviderConfigured,
                approvalAvailable,
                decisionAvailabilityCheckAttempted,
                decisionEvaluatedCheckAttempted,
                evidenceCheckAttempted);
    }
}

package lab.healthcare.fhir.aiconsumerenforcementverificationapproval;

/**
 * Stable verification-approval reason codes. Never include clinical
 * values or vendor names.
 */
public final class AiConsumerEnforcementVerificationApprovalReasonCodes {

    public static final String VERIFICATION_DECISION_RESULT_MISSING =
            "VERIFICATION_DECISION_RESULT_MISSING";
    public static final String VERIFICATION_APPROVAL_CONTEXT_MISSING =
            "VERIFICATION_APPROVAL_CONTEXT_MISSING";
    public static final String SYNTHETIC_APPROVAL_CLAIMS_UNTRUSTED =
            "SYNTHETIC_APPROVAL_CLAIMS_UNTRUSTED";
    public static final String VERIFICATION_DECISION_NOT_AVAILABLE =
            "VERIFICATION_DECISION_NOT_AVAILABLE";
    public static final String VERIFICATION_DECISION_NOT_EVALUATED =
            "VERIFICATION_DECISION_NOT_EVALUATED";
    public static final String HUMAN_REVIEW_REQUIRED_BY_PREVIOUS_BOUNDARY =
            "HUMAN_REVIEW_REQUIRED_BY_PREVIOUS_BOUNDARY";
    public static final String VERIFICATION_APPROVAL_EVIDENCE_NOT_AVAILABLE =
            "VERIFICATION_APPROVAL_EVIDENCE_NOT_AVAILABLE";
    public static final String VERIFICATION_APPROVAL_NOT_AVAILABLE =
            "VERIFICATION_APPROVAL_NOT_AVAILABLE";

    private AiConsumerEnforcementVerificationApprovalReasonCodes() {
    }
}

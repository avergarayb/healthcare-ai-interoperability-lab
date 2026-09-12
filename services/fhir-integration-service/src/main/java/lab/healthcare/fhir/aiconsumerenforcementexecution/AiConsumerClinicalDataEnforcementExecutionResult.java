package lab.healthcare.fhir.aiconsumerenforcementexecution;

/**
 * Clinical data-access enforcement-execution verdict. Never includes
 * tokens, Patient identifiers, or FHIR JSON. A synthetic execution
 * claim is not a grant and is not a FHIR read.
 */
public record AiConsumerClinicalDataEnforcementExecutionResult(
        String boundaryVersion,
        AiConsumerClinicalDataEnforcementExecutionStatus status,
        String reason,
        String operation,
        boolean inputAvailable,
        String requestSource,
        String executionEvaluationStatus,
        String decisionReason,
        boolean executionDecisionAvailable,
        boolean executionDecisionEvaluated,
        boolean enforcementExecutionAvailable,
        boolean enforcementExecutionProviderConfigured,
        boolean enforcementExecutionPerformed,
        boolean realAuthorizationRequired,
        boolean clinicalDataAccessGranted,
        boolean clinicalDataAccessAllowed,
        boolean clinicalDataAccessEnforced,
        boolean enforcementDecisionAvailable,
        boolean enforcementDecisionEvaluated,
        boolean clinicalDataAccessEnforcementAvailable,
        boolean clinicalDataAccessEnforcementProviderConfigured,
        boolean clinicalDataAccessEnforcementExecuted,
        boolean accessRequestEvaluated,
        boolean clinicalDataAccessRequested,
        boolean clinicalDataAccessGrantAvailable,
        boolean clinicalDataAccessProviderConfigured,
        boolean clinicalDataAccessAuthorizationAvailable,
        boolean scopeEvaluated,
        boolean minimizationEvaluated,
        boolean purposeScopeAlignmentEvaluated,
        boolean clinicalDataScopeProviderConfigured,
        boolean clinicalDataScopeApprovalAvailable,
        boolean consentVerified,
        boolean purposeApproved,
        boolean dataScopeApproved,
        boolean consentProviderConfigured,
        boolean consentAvailable,
        boolean authenticationVerified,
        boolean authorizationGranted,
        boolean realSecurityProviderConfigured,
        boolean consumerAuthorizationAvailable,
        boolean handoffAuthorized,
        boolean dispatchPerformed,
        boolean externalAuthorizationAvailable,
        boolean modelCallAuthorized,
        boolean modelCalled,
        String processingStatus,
        String dispatchStatus,
        boolean requiresHumanReview) {

    public static final String NOT_EXECUTED = "NOT_EXECUTED";
    public static final String NOT_DISPATCHED = "NOT_DISPATCHED";
    public static final String VERSION_V1 = "v1";
    public static final String EVALUATION_NOT_EVALUATED = "NOT_EVALUATED";

    static AiConsumerClinicalDataEnforcementExecutionResult denied(
            AiConsumerClinicalDataEnforcementExecutionStatus status,
            String reason,
            boolean inputAvailable,
            String requestSource) {
        return new AiConsumerClinicalDataEnforcementExecutionResult(
                VERSION_V1,
                status,
                reason,
                AiConsumerClinicalDataEnforcementExecutionOperations.EVALUATE_CLINICAL_DATA_ENFORCEMENT_EXECUTION,
                inputAvailable,
                requestSource,
                EVALUATION_NOT_EVALUATED,
                reason,
                false,
                false,
                false,
                false,
                false,
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
                false,
                false,
                NOT_EXECUTED,
                NOT_DISPATCHED,
                true);
    }

    public AiConsumerClinicalDataEnforcementExecutionResult {
        if (status == null) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement execution status must be provided");
        }
        if (executionDecisionAvailable) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement execution has no decision");
        }
        if (executionDecisionEvaluated) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement execution must not evaluate a decision");
        }
        if (enforcementExecutionAvailable) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement execution is not available");
        }
        if (enforcementExecutionProviderConfigured) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement execution has no provider");
        }
        if (enforcementExecutionPerformed) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement execution must not perform execution");
        }
        if (!realAuthorizationRequired) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement execution requires real authorization");
        }
        if (clinicalDataAccessGranted) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement execution must not grant clinical access");
        }
        if (clinicalDataAccessAllowed) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement execution must not allow clinical data access");
        }
        if (clinicalDataAccessEnforced) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement execution must not enforce access");
        }
        if (enforcementDecisionAvailable) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement execution has no enforcement decision");
        }
        if (enforcementDecisionEvaluated) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement execution must not evaluate enforcement");
        }
        if (clinicalDataAccessEnforcementAvailable) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement execution has no enforcement");
        }
        if (clinicalDataAccessEnforcementProviderConfigured) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement execution has no enforcement provider");
        }
        if (clinicalDataAccessEnforcementExecuted) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement execution must not execute enforcement");
        }
        if (accessRequestEvaluated) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement execution must not evaluate a request");
        }
        if (clinicalDataAccessRequested) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement execution must not request clinical access");
        }
        if (clinicalDataAccessGrantAvailable) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement execution grant is not available");
        }
        if (clinicalDataAccessProviderConfigured) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement execution has no access provider");
        }
        if (clinicalDataAccessAuthorizationAvailable) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement execution has no authorization");
        }
        if (scopeEvaluated) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement execution must not evaluate a scope");
        }
        if (minimizationEvaluated) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement execution must not evaluate minimization");
        }
        if (purposeScopeAlignmentEvaluated) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement execution must not evaluate purpose-scope alignment");
        }
        if (clinicalDataScopeProviderConfigured) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement execution has no scope provider");
        }
        if (clinicalDataScopeApprovalAvailable) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement execution approval is not available");
        }
        if (consentVerified) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement execution must not verify consent");
        }
        if (purposeApproved) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement execution must not approve a purpose");
        }
        if (dataScopeApproved) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement execution must not approve a data scope");
        }
        if (consentProviderConfigured) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement execution has no consent provider");
        }
        if (consentAvailable) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement execution has no consent");
        }
        if (authenticationVerified) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement execution must not verify authentication");
        }
        if (authorizationGranted) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement execution must not grant authorization");
        }
        if (realSecurityProviderConfigured) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement execution has no real security provider");
        }
        if (consumerAuthorizationAvailable) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement execution has no consumer authorization");
        }
        if (handoffAuthorized) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement execution must not authorize handoff");
        }
        if (dispatchPerformed) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement execution must not perform dispatch");
        }
        if (externalAuthorizationAvailable) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement execution has no external authorization");
        }
        if (modelCallAuthorized) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement execution must not authorize a model call");
        }
        if (modelCalled) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement execution must not call a model");
        }
        if (!NOT_EXECUTED.equals(blankToEmpty(processingStatus))) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement execution must not execute model processing");
        }
        if (!NOT_DISPATCHED.equals(blankToEmpty(dispatchStatus))) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement execution must not dispatch");
        }
        if (!requiresHumanReview) {
            throw new IllegalArgumentException("AI consumer clinical data-enforcement execution requires human review");
        }
        boundaryVersion = VERSION_V1;
        reason = blankToEmpty(reason);
        operation = blankToEmpty(operation);
        requestSource = blankToEmpty(requestSource);
        executionEvaluationStatus = EVALUATION_NOT_EVALUATED;
        decisionReason = blankToEmpty(decisionReason);
        processingStatus = NOT_EXECUTED;
        dispatchStatus = NOT_DISPATCHED;
    }

    private static String blankToEmpty(String value) {
        return value == null ? "" : value.trim();
    }
}

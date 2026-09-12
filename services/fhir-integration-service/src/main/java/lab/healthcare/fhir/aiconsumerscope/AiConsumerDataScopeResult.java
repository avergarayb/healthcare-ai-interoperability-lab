package lab.healthcare.fhir.aiconsumerscope;

import java.util.List;

/**
 * Clinical data-scope and minimization verdict. Never includes tokens,
 * Patient identifiers, or FHIR JSON. A declared scope is not approval
 * and is not clinical access.
 */
public record AiConsumerDataScopeResult(
        String boundaryVersion,
        AiConsumerDataScopeStatus status,
        String reason,
        String operation,
        boolean inputAvailable,
        String scopeDeclarationSource,
        List<String> declaredDataCategories,
        List<String> declaredResourceTypes,
        String declaredTenantScope,
        boolean scopeDeclared,
        boolean scopeEvaluated,
        boolean minimizationEvaluated,
        boolean purposeScopeAlignmentEvaluated,
        String minimizationStatus,
        PurposeScopeAlignmentStatus purposeScopeAlignmentStatus,
        boolean clinicalDataScopeProviderConfigured,
        boolean clinicalDataScopeApprovalAvailable,
        boolean clinicalDataAccessRequested,
        boolean clinicalDataAccessGranted,
        boolean clinicalDataAccessAllowed,
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
    public static final String MINIMIZATION_NOT_EVALUATED = "NOT_EVALUATED";

    public AiConsumerDataScopeResult {
        if (status == null) {
            throw new IllegalArgumentException("AI consumer data-scope status must be provided");
        }
        if (purposeScopeAlignmentStatus == null) {
            throw new IllegalArgumentException("Purpose-scope alignment status must be provided");
        }
        if (scopeEvaluated) {
            throw new IllegalArgumentException("AI consumer data-scope must not evaluate a scope");
        }
        if (minimizationEvaluated) {
            throw new IllegalArgumentException("AI consumer data-scope must not evaluate minimization");
        }
        if (purposeScopeAlignmentEvaluated) {
            throw new IllegalArgumentException("AI consumer data-scope must not evaluate purpose-scope alignment");
        }
        if (clinicalDataScopeProviderConfigured) {
            throw new IllegalArgumentException("AI consumer data-scope has no scope provider");
        }
        if (clinicalDataScopeApprovalAvailable) {
            throw new IllegalArgumentException("AI consumer data-scope approval is not available");
        }
        if (clinicalDataAccessRequested) {
            throw new IllegalArgumentException("AI consumer data-scope must not request clinical access");
        }
        if (clinicalDataAccessGranted) {
            throw new IllegalArgumentException("AI consumer data-scope must not grant clinical access");
        }
        if (clinicalDataAccessAllowed) {
            throw new IllegalArgumentException("AI consumer data-scope must not allow clinical data access");
        }
        if (consentVerified) {
            throw new IllegalArgumentException("AI consumer data-scope must not verify consent");
        }
        if (purposeApproved) {
            throw new IllegalArgumentException("AI consumer data-scope must not approve a purpose");
        }
        if (dataScopeApproved) {
            throw new IllegalArgumentException("AI consumer data-scope must not approve a data scope");
        }
        if (consentProviderConfigured) {
            throw new IllegalArgumentException("AI consumer data-scope has no consent provider");
        }
        if (consentAvailable) {
            throw new IllegalArgumentException("AI consumer data-scope has no consent");
        }
        if (authenticationVerified) {
            throw new IllegalArgumentException("AI consumer data-scope must not verify authentication");
        }
        if (authorizationGranted) {
            throw new IllegalArgumentException("AI consumer data-scope must not grant authorization");
        }
        if (realSecurityProviderConfigured) {
            throw new IllegalArgumentException("AI consumer data-scope has no real security provider");
        }
        if (consumerAuthorizationAvailable) {
            throw new IllegalArgumentException("AI consumer data-scope has no consumer authorization");
        }
        if (handoffAuthorized) {
            throw new IllegalArgumentException("AI consumer data-scope must not authorize handoff");
        }
        if (dispatchPerformed) {
            throw new IllegalArgumentException("AI consumer data-scope must not perform dispatch");
        }
        if (externalAuthorizationAvailable) {
            throw new IllegalArgumentException("AI consumer data-scope has no external authorization");
        }
        if (modelCallAuthorized) {
            throw new IllegalArgumentException("AI consumer data-scope must not authorize a model call");
        }
        if (modelCalled) {
            throw new IllegalArgumentException("AI consumer data-scope must not call a model");
        }
        if (!NOT_EXECUTED.equals(blankToEmpty(processingStatus))) {
            throw new IllegalArgumentException("AI consumer data-scope must not execute model processing");
        }
        if (!NOT_DISPATCHED.equals(blankToEmpty(dispatchStatus))) {
            throw new IllegalArgumentException("AI consumer data-scope must not dispatch");
        }
        if (!requiresHumanReview) {
            throw new IllegalArgumentException("AI consumer data-scope requires human review");
        }
        boundaryVersion = VERSION_V1;
        reason = blankToEmpty(reason);
        operation = blankToEmpty(operation);
        scopeDeclarationSource = blankToEmpty(scopeDeclarationSource);
        declaredTenantScope = blankToEmpty(declaredTenantScope);
        minimizationStatus = MINIMIZATION_NOT_EVALUATED;
        declaredDataCategories = declaredDataCategories == null ? List.of() : List.copyOf(declaredDataCategories);
        declaredResourceTypes = declaredResourceTypes == null ? List.of() : List.copyOf(declaredResourceTypes);
        processingStatus = NOT_EXECUTED;
        dispatchStatus = NOT_DISPATCHED;
    }

    private static String blankToEmpty(String value) {
        return value == null ? "" : value.trim();
    }
}

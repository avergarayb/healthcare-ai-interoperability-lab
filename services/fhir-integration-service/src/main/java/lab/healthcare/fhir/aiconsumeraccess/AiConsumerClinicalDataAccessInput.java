package lab.healthcare.fhir.aiconsumeraccess;

import lab.healthcare.fhir.aiconsumerscope.AiConsumerDataScopeResult;

/**
 * Access-request input copied from a data-scope result plus a synthetic
 * request context. Unlike the 067 result, this record may hold
 * {@code clinicalDataAccessAllowed=true} so the boundary can detect
 * that flag instead of silently accepting it.
 */
public record AiConsumerClinicalDataAccessInput(
        boolean dataScopeResultPresent,
        boolean scopeDeclared,
        boolean scopeEvaluated,
        boolean clinicalDataScopeApprovalAvailable,
        boolean consentVerified,
        boolean purposeApproved,
        boolean clinicalDataAccessRequested,
        boolean clinicalDataAccessGranted,
        boolean clinicalDataAccessAllowed,
        boolean requiresHumanReview,
        String declaredTenantScope,
        ClinicalDataAccessRequestContext request) {

    public static AiConsumerClinicalDataAccessInput from(AiConsumerDataScopeResult scope) {
        if (scope == null) {
            return null;
        }
        return new AiConsumerClinicalDataAccessInput(
                true,
                scope.scopeDeclared(),
                scope.scopeEvaluated(),
                scope.clinicalDataScopeApprovalAvailable(),
                scope.consentVerified(),
                scope.purposeApproved(),
                scope.clinicalDataAccessRequested(),
                scope.clinicalDataAccessGranted(),
                scope.clinicalDataAccessAllowed(),
                scope.requiresHumanReview(),
                scope.declaredTenantScope(),
                ClinicalDataAccessRequestContext.laboratory());
    }

    public static AiConsumerClinicalDataAccessInput of(
            AiConsumerDataScopeResult scope, ClinicalDataAccessRequestContext request) {
        if (scope == null) {
            return null;
        }
        return new AiConsumerClinicalDataAccessInput(
                true,
                scope.scopeDeclared(),
                scope.scopeEvaluated(),
                scope.clinicalDataScopeApprovalAvailable(),
                scope.consentVerified(),
                scope.purposeApproved(),
                scope.clinicalDataAccessRequested(),
                scope.clinicalDataAccessGranted(),
                scope.clinicalDataAccessAllowed(),
                scope.requiresHumanReview(),
                scope.declaredTenantScope(),
                request == null ? ClinicalDataAccessRequestContext.laboratory() : request);
    }

    public AiConsumerClinicalDataAccessInput withClinicalDataAccessAllowed(boolean value) {
        return new AiConsumerClinicalDataAccessInput(
                dataScopeResultPresent,
                scopeDeclared,
                scopeEvaluated,
                clinicalDataScopeApprovalAvailable,
                consentVerified,
                purposeApproved,
                clinicalDataAccessRequested,
                clinicalDataAccessGranted,
                value,
                requiresHumanReview,
                declaredTenantScope,
                request);
    }

    public AiConsumerClinicalDataAccessInput withClinicalDataAccessGranted(boolean value) {
        return new AiConsumerClinicalDataAccessInput(
                dataScopeResultPresent,
                scopeDeclared,
                scopeEvaluated,
                clinicalDataScopeApprovalAvailable,
                consentVerified,
                purposeApproved,
                clinicalDataAccessRequested,
                value,
                clinicalDataAccessAllowed,
                requiresHumanReview,
                declaredTenantScope,
                request);
    }
}

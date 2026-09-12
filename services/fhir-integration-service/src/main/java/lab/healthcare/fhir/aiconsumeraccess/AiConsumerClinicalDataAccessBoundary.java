package lab.healthcare.fhir.aiconsumeraccess;

import lab.healthcare.fhir.aiconsumerscope.AiConsumerDataScopeResult;

/**
 * Deny-by-default clinical data-access request boundary.
 * A declared request is not an evaluated request. An effective
 * synthetic request is not a grant. Task 068 never reads FHIR.
 */
public final class AiConsumerClinicalDataAccessBoundary {

    private AiConsumerClinicalDataAccessBoundary() {
    }

    public static AiConsumerClinicalDataAccessResult evaluate(AiConsumerDataScopeResult scope) {
        if (scope == null) {
            return missingScope();
        }
        return evaluate(AiConsumerClinicalDataAccessInput.from(scope));
    }

    public static AiConsumerClinicalDataAccessResult evaluate(
            AiConsumerDataScopeResult scope, ClinicalDataAccessRequestContext request) {
        if (scope == null) {
            return missingScope();
        }
        return evaluate(AiConsumerClinicalDataAccessInput.of(scope, request));
    }

    public static AiConsumerClinicalDataAccessResult evaluate(AiConsumerClinicalDataAccessInput input) {
        if (input == null || !input.dataScopeResultPresent()) {
            return missingScope();
        }
        ClinicalDataAccessRequestContext request =
                input.request() == null ? ClinicalDataAccessRequestContext.laboratory() : input.request();
        if (untrustedAssertion(input, request)) {
            return result(
                    AiConsumerClinicalDataAccessStatus.ACCESS_REQUEST_BLOCKED,
                    AiConsumerClinicalDataAccessReasonCodes.UNTRUSTED_ACCESS_ASSERTION,
                    input,
                    request,
                    false);
        }
        if (request.contextPresent() && !request.tenantScopePresent()) {
            return result(
                    AiConsumerClinicalDataAccessStatus.ACCESS_REQUEST_BLOCKED,
                    AiConsumerClinicalDataAccessReasonCodes.MISSING_TENANT_SCOPE,
                    input,
                    request,
                    false);
        }
        boolean requestPresent = request.requestDeclared() || request.effectiveRequestClaim();
        boolean scopeReference = request.scopeReferencePresent() || input.scopeDeclared();
        if (requestPresent && !scopeReference) {
            return result(
                    AiConsumerClinicalDataAccessStatus.ACCESS_REQUEST_REQUIRES_SCOPE,
                    AiConsumerClinicalDataAccessReasonCodes.ACCESS_REQUEST_REQUIRES_SCOPE,
                    input,
                    request,
                    false);
        }
        if (request.effectiveRequestClaim()) {
            return result(
                    AiConsumerClinicalDataAccessStatus.ACCESS_REQUEST_REQUIRES_REAL_AUTHORIZATION,
                    AiConsumerClinicalDataAccessReasonCodes.ACCESS_REQUEST_REQUIRES_REAL_AUTHORIZATION,
                    input,
                    request,
                    true);
        }
        if (request.requestDeclared()) {
            return result(
                    AiConsumerClinicalDataAccessStatus.ACCESS_REQUEST_DECLARED_NOT_EVALUATED,
                    AiConsumerClinicalDataAccessReasonCodes.ACCESS_REQUEST_DECLARED_NOT_EVALUATED,
                    input,
                    request,
                    false);
        }
        if (request.declarationAttempted()) {
            return result(
                    AiConsumerClinicalDataAccessStatus.ACCESS_REQUEST_NOT_DECLARED,
                    AiConsumerClinicalDataAccessReasonCodes.ACCESS_REQUEST_NOT_DECLARED,
                    input,
                    request,
                    false);
        }
        if (!input.scopeEvaluated() || !input.clinicalDataScopeApprovalAvailable()) {
            return result(
                    AiConsumerClinicalDataAccessStatus.NOT_GRANTED_FOR_CLINICAL_DATA_ACCESS,
                    AiConsumerClinicalDataAccessReasonCodes.SCOPE_NOT_PREPARED,
                    input,
                    request,
                    false);
        }
        if (!input.consentVerified() || !input.purposeApproved()) {
            return result(
                    AiConsumerClinicalDataAccessStatus.ACCESS_REQUEST_REQUIRES_HUMAN_REVIEW,
                    AiConsumerClinicalDataAccessReasonCodes.NOT_GRANTED_FOR_CLINICAL_DATA_ACCESS,
                    input,
                    request,
                    false);
        }
        return result(
                AiConsumerClinicalDataAccessStatus.NOT_GRANTED_FOR_CLINICAL_DATA_ACCESS,
                AiConsumerClinicalDataAccessReasonCodes.NOT_GRANTED_FOR_CLINICAL_DATA_ACCESS,
                input,
                request,
                false);
    }

    private static boolean untrustedAssertion(
            AiConsumerClinicalDataAccessInput input, ClinicalDataAccessRequestContext request) {
        return input.clinicalDataAccessGranted()
                || input.clinicalDataAccessAllowed()
                || input.consentVerified()
                || input.purposeApproved()
                || request.accessRequestEvaluatedClaim()
                || request.clinicalDataAccessGrantedClaim()
                || request.clinicalDataAccessAllowedClaim()
                || request.clinicalDataAccessGrantAvailableClaim()
                || request.clinicalDataAccessEnforcedClaim()
                || request.clinicalDataAccessProviderConfigured()
                || request.clinicalDataAccessAuthorizationAvailable();
    }

    private static AiConsumerClinicalDataAccessResult missingScope() {
        return result(
                AiConsumerClinicalDataAccessStatus.ACCESS_REQUEST_BLOCKED,
                AiConsumerClinicalDataAccessReasonCodes.MISSING_DATA_SCOPE_RESULT,
                null,
                ClinicalDataAccessRequestContext.laboratory(),
                false);
    }

    private static AiConsumerClinicalDataAccessResult result(
            AiConsumerClinicalDataAccessStatus status,
            String reason,
            AiConsumerClinicalDataAccessInput input,
            ClinicalDataAccessRequestContext request,
            boolean effectiveRequested) {
        boolean declared = request.requestDeclared() || request.effectiveRequestClaim();
        boolean scopeReference = request.scopeReferencePresent() || (input != null && input.scopeDeclared());
        return AiConsumerClinicalDataAccessResult.denied(
                status,
                reason,
                input != null && input.dataScopeResultPresent(),
                declared
                        ? ClinicalDataAccessRequestContext.SOURCE_SYNTHETIC_REQUEST
                        : ClinicalDataAccessRequestContext.SOURCE_LABORATORY,
                request.requestedDataCategories(),
                request.requestedResourceTypes(),
                request.requestedTenantScope(),
                declared,
                scopeReference,
                effectiveRequested);
    }
}

package lab.healthcare.fhir.aiconsumeraccess;

import java.util.List;

/**
 * Synthetic, untrusted clinical access-request metadata. Declaring a
 * request is not evaluation and is not a grant. Never includes Patient
 * identifiers, tokens, or FHIR JSON.
 */
public record ClinicalDataAccessRequestContext(
        boolean contextPresent,
        boolean declarationAttempted,
        boolean requestDeclared,
        boolean effectiveRequestClaim,
        boolean scopeReferencePresent,
        List<String> requestedDataCategories,
        List<String> requestedResourceTypes,
        boolean tenantScopePresent,
        String requestedTenantScope,
        boolean accessRequestEvaluatedClaim,
        boolean clinicalDataAccessGrantedClaim,
        boolean clinicalDataAccessAllowedClaim,
        boolean clinicalDataAccessGrantAvailableClaim,
        boolean clinicalDataAccessEnforcedClaim,
        boolean clinicalDataAccessProviderConfigured,
        boolean clinicalDataAccessAuthorizationAvailable) {

    public static final String SOURCE_LABORATORY = "LABORATORY";
    public static final String SOURCE_SYNTHETIC_REQUEST = "SYNTHETIC_REQUEST";

    public ClinicalDataAccessRequestContext {
        requestedDataCategories = requestedDataCategories == null
                ? List.of()
                : List.copyOf(requestedDataCategories);
        requestedResourceTypes = requestedResourceTypes == null
                ? List.of()
                : List.copyOf(requestedResourceTypes.stream()
                        .filter(value -> value != null && !value.isBlank())
                        .map(String::trim)
                        .toList());
        requestedTenantScope = requestedTenantScope == null ? "" : requestedTenantScope.trim();
    }

    public static ClinicalDataAccessRequestContext laboratory() {
        return new ClinicalDataAccessRequestContext(
                true,
                false,
                false,
                false,
                false,
                List.of(),
                List.of(),
                true,
                "LAB",
                false,
                false,
                false,
                false,
                false,
                false,
                false);
    }

    public ClinicalDataAccessRequestContext withDeclarationAttempted(boolean value) {
        return copy(
                contextPresent,
                value,
                requestDeclared,
                effectiveRequestClaim,
                scopeReferencePresent,
                requestedDataCategories,
                requestedResourceTypes,
                tenantScopePresent,
                requestedTenantScope,
                accessRequestEvaluatedClaim,
                clinicalDataAccessGrantedClaim,
                clinicalDataAccessAllowedClaim,
                clinicalDataAccessGrantAvailableClaim,
                clinicalDataAccessEnforcedClaim,
                clinicalDataAccessProviderConfigured,
                clinicalDataAccessAuthorizationAvailable);
    }

    public ClinicalDataAccessRequestContext withRequestDeclared(boolean value) {
        return copy(
                contextPresent,
                declarationAttempted,
                value,
                effectiveRequestClaim,
                scopeReferencePresent,
                requestedDataCategories,
                requestedResourceTypes,
                tenantScopePresent,
                requestedTenantScope,
                accessRequestEvaluatedClaim,
                clinicalDataAccessGrantedClaim,
                clinicalDataAccessAllowedClaim,
                clinicalDataAccessGrantAvailableClaim,
                clinicalDataAccessEnforcedClaim,
                clinicalDataAccessProviderConfigured,
                clinicalDataAccessAuthorizationAvailable);
    }

    public ClinicalDataAccessRequestContext withEffectiveRequestClaim(boolean value) {
        return copy(
                contextPresent,
                declarationAttempted,
                requestDeclared,
                value,
                scopeReferencePresent,
                requestedDataCategories,
                requestedResourceTypes,
                tenantScopePresent,
                requestedTenantScope,
                accessRequestEvaluatedClaim,
                clinicalDataAccessGrantedClaim,
                clinicalDataAccessAllowedClaim,
                clinicalDataAccessGrantAvailableClaim,
                clinicalDataAccessEnforcedClaim,
                clinicalDataAccessProviderConfigured,
                clinicalDataAccessAuthorizationAvailable);
    }

    public ClinicalDataAccessRequestContext withScopeReferencePresent(boolean value) {
        return copy(
                contextPresent,
                declarationAttempted,
                requestDeclared,
                effectiveRequestClaim,
                value,
                requestedDataCategories,
                requestedResourceTypes,
                tenantScopePresent,
                requestedTenantScope,
                accessRequestEvaluatedClaim,
                clinicalDataAccessGrantedClaim,
                clinicalDataAccessAllowedClaim,
                clinicalDataAccessGrantAvailableClaim,
                clinicalDataAccessEnforcedClaim,
                clinicalDataAccessProviderConfigured,
                clinicalDataAccessAuthorizationAvailable);
    }

    public ClinicalDataAccessRequestContext withTenantScopePresent(boolean value) {
        return copy(
                contextPresent,
                declarationAttempted,
                requestDeclared,
                effectiveRequestClaim,
                scopeReferencePresent,
                requestedDataCategories,
                requestedResourceTypes,
                value,
                requestedTenantScope,
                accessRequestEvaluatedClaim,
                clinicalDataAccessGrantedClaim,
                clinicalDataAccessAllowedClaim,
                clinicalDataAccessGrantAvailableClaim,
                clinicalDataAccessEnforcedClaim,
                clinicalDataAccessProviderConfigured,
                clinicalDataAccessAuthorizationAvailable);
    }

    public ClinicalDataAccessRequestContext withGrantedClaim(boolean value) {
        return copy(
                contextPresent,
                declarationAttempted,
                requestDeclared,
                effectiveRequestClaim,
                scopeReferencePresent,
                requestedDataCategories,
                requestedResourceTypes,
                tenantScopePresent,
                requestedTenantScope,
                accessRequestEvaluatedClaim,
                value,
                clinicalDataAccessAllowedClaim,
                clinicalDataAccessGrantAvailableClaim,
                clinicalDataAccessEnforcedClaim,
                clinicalDataAccessProviderConfigured,
                clinicalDataAccessAuthorizationAvailable);
    }

    public ClinicalDataAccessRequestContext withAllowedClaim(boolean value) {
        return copy(
                contextPresent,
                declarationAttempted,
                requestDeclared,
                effectiveRequestClaim,
                scopeReferencePresent,
                requestedDataCategories,
                requestedResourceTypes,
                tenantScopePresent,
                requestedTenantScope,
                accessRequestEvaluatedClaim,
                clinicalDataAccessGrantedClaim,
                value,
                clinicalDataAccessGrantAvailableClaim,
                clinicalDataAccessEnforcedClaim,
                clinicalDataAccessProviderConfigured,
                clinicalDataAccessAuthorizationAvailable);
    }

    public ClinicalDataAccessRequestContext withEvaluatedClaim(boolean value) {
        return copy(
                contextPresent,
                declarationAttempted,
                requestDeclared,
                effectiveRequestClaim,
                scopeReferencePresent,
                requestedDataCategories,
                requestedResourceTypes,
                tenantScopePresent,
                requestedTenantScope,
                value,
                clinicalDataAccessGrantedClaim,
                clinicalDataAccessAllowedClaim,
                clinicalDataAccessGrantAvailableClaim,
                clinicalDataAccessEnforcedClaim,
                clinicalDataAccessProviderConfigured,
                clinicalDataAccessAuthorizationAvailable);
    }

    private ClinicalDataAccessRequestContext copy(
            boolean contextPresent,
            boolean declarationAttempted,
            boolean requestDeclared,
            boolean effectiveRequestClaim,
            boolean scopeReferencePresent,
            List<String> requestedDataCategories,
            List<String> requestedResourceTypes,
            boolean tenantScopePresent,
            String requestedTenantScope,
            boolean accessRequestEvaluatedClaim,
            boolean clinicalDataAccessGrantedClaim,
            boolean clinicalDataAccessAllowedClaim,
            boolean clinicalDataAccessGrantAvailableClaim,
            boolean clinicalDataAccessEnforcedClaim,
            boolean clinicalDataAccessProviderConfigured,
            boolean clinicalDataAccessAuthorizationAvailable) {
        return new ClinicalDataAccessRequestContext(
                contextPresent,
                declarationAttempted,
                requestDeclared,
                effectiveRequestClaim,
                scopeReferencePresent,
                requestedDataCategories,
                requestedResourceTypes,
                tenantScopePresent,
                requestedTenantScope,
                accessRequestEvaluatedClaim,
                clinicalDataAccessGrantedClaim,
                clinicalDataAccessAllowedClaim,
                clinicalDataAccessGrantAvailableClaim,
                clinicalDataAccessEnforcedClaim,
                clinicalDataAccessProviderConfigured,
                clinicalDataAccessAuthorizationAvailable);
    }
}

package lab.healthcare.fhir.aiconsumerscope;

import java.util.List;

/**
 * Synthetic, untrusted clinical data-scope metadata. Declaring categories
 * is not evaluation and is not clinical access. Never includes Patient
 * identifiers, tokens, or FHIR JSON.
 */
public record ConsumerDataScopeContext(
        boolean contextPresent,
        boolean declarationAttempted,
        List<ConsumerDataScopeCategories> declaredDataCategories,
        List<String> declaredResourceTypes,
        boolean tenantScopePresent,
        String declaredTenantScope,
        boolean scopeEvaluatedClaim,
        boolean minimizationEvaluatedClaim,
        boolean purposeScopeAlignmentEvaluatedClaim,
        boolean clinicalDataScopeProviderConfigured,
        boolean clinicalDataScopeApprovalAvailable,
        boolean clinicalDataAccessRequested,
        boolean clinicalDataAccessGranted,
        boolean clinicalDataAccessAllowedClaim) {

    public static final String BOUNDARY_VERSION = "v1";
    public static final String SOURCE_LABORATORY = "LABORATORY";
    public static final String SOURCE_SYNTHETIC_DECLARATION = "SYNTHETIC_DECLARATION";

    public ConsumerDataScopeContext {
        declaredDataCategories = declaredDataCategories == null
                ? List.of()
                : List.copyOf(declaredDataCategories);
        declaredResourceTypes = declaredResourceTypes == null
                ? List.of()
                : List.copyOf(declaredResourceTypes.stream()
                        .filter(value -> value != null && !value.isBlank())
                        .map(String::trim)
                        .toList());
        declaredTenantScope = declaredTenantScope == null ? "" : declaredTenantScope.trim();
    }

    /**
     * Laboratory context. No clinical categories are declared, so a future
     * scope evaluation has not started. Tenant metadata is present and
     * untrusted.
     */
    public static ConsumerDataScopeContext laboratory() {
        return new ConsumerDataScopeContext(
                true,
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
                false,
                false);
    }

    public ConsumerDataScopeContext withDeclarationAttempted(boolean value) {
        return copy(
                contextPresent,
                value,
                declaredDataCategories,
                declaredResourceTypes,
                tenantScopePresent,
                declaredTenantScope,
                scopeEvaluatedClaim,
                minimizationEvaluatedClaim,
                purposeScopeAlignmentEvaluatedClaim,
                clinicalDataScopeProviderConfigured,
                clinicalDataScopeApprovalAvailable,
                clinicalDataAccessRequested,
                clinicalDataAccessGranted,
                clinicalDataAccessAllowedClaim);
    }

    public ConsumerDataScopeContext withDeclaredDataCategories(List<ConsumerDataScopeCategories> value) {
        return copy(
                contextPresent,
                declarationAttempted,
                value,
                declaredResourceTypes,
                tenantScopePresent,
                declaredTenantScope,
                scopeEvaluatedClaim,
                minimizationEvaluatedClaim,
                purposeScopeAlignmentEvaluatedClaim,
                clinicalDataScopeProviderConfigured,
                clinicalDataScopeApprovalAvailable,
                clinicalDataAccessRequested,
                clinicalDataAccessGranted,
                clinicalDataAccessAllowedClaim);
    }

    public ConsumerDataScopeContext withTenantScopePresent(boolean value) {
        return copy(
                contextPresent,
                declarationAttempted,
                declaredDataCategories,
                declaredResourceTypes,
                value,
                declaredTenantScope,
                scopeEvaluatedClaim,
                minimizationEvaluatedClaim,
                purposeScopeAlignmentEvaluatedClaim,
                clinicalDataScopeProviderConfigured,
                clinicalDataScopeApprovalAvailable,
                clinicalDataAccessRequested,
                clinicalDataAccessGranted,
                clinicalDataAccessAllowedClaim);
    }

    public ConsumerDataScopeContext withClinicalDataAccessAllowedClaim(boolean value) {
        return copy(
                contextPresent,
                declarationAttempted,
                declaredDataCategories,
                declaredResourceTypes,
                tenantScopePresent,
                declaredTenantScope,
                scopeEvaluatedClaim,
                minimizationEvaluatedClaim,
                purposeScopeAlignmentEvaluatedClaim,
                clinicalDataScopeProviderConfigured,
                clinicalDataScopeApprovalAvailable,
                clinicalDataAccessRequested,
                clinicalDataAccessGranted,
                value);
    }

    public ConsumerDataScopeContext withScopeEvaluatedClaim(boolean value) {
        return copy(
                contextPresent,
                declarationAttempted,
                declaredDataCategories,
                declaredResourceTypes,
                tenantScopePresent,
                declaredTenantScope,
                value,
                minimizationEvaluatedClaim,
                purposeScopeAlignmentEvaluatedClaim,
                clinicalDataScopeProviderConfigured,
                clinicalDataScopeApprovalAvailable,
                clinicalDataAccessRequested,
                clinicalDataAccessGranted,
                clinicalDataAccessAllowedClaim);
    }

    public boolean hasDeclaredScope() {
        return !declaredDataCategories.isEmpty() || !declaredResourceTypes.isEmpty();
    }

    private ConsumerDataScopeContext copy(
            boolean contextPresent,
            boolean declarationAttempted,
            List<ConsumerDataScopeCategories> declaredDataCategories,
            List<String> declaredResourceTypes,
            boolean tenantScopePresent,
            String declaredTenantScope,
            boolean scopeEvaluatedClaim,
            boolean minimizationEvaluatedClaim,
            boolean purposeScopeAlignmentEvaluatedClaim,
            boolean clinicalDataScopeProviderConfigured,
            boolean clinicalDataScopeApprovalAvailable,
            boolean clinicalDataAccessRequested,
            boolean clinicalDataAccessGranted,
            boolean clinicalDataAccessAllowedClaim) {
        return new ConsumerDataScopeContext(
                contextPresent,
                declarationAttempted,
                declaredDataCategories,
                declaredResourceTypes,
                tenantScopePresent,
                declaredTenantScope,
                scopeEvaluatedClaim,
                minimizationEvaluatedClaim,
                purposeScopeAlignmentEvaluatedClaim,
                clinicalDataScopeProviderConfigured,
                clinicalDataScopeApprovalAvailable,
                clinicalDataAccessRequested,
                clinicalDataAccessGranted,
                clinicalDataAccessAllowedClaim);
    }
}

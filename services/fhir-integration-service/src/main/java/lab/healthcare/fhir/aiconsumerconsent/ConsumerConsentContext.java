package lab.healthcare.fhir.aiconsumerconsent;

/**
 * Synthetic, untrusted consent and purpose metadata. Presence of a field
 * is not verified consent and is not clinical access. Never includes
 * Patient identifiers, signatures, tokens, or FHIR JSON.
 */
public record ConsumerConsentContext(
        boolean contextPresent,
        boolean consentReferencePresent,
        boolean consentVerified,
        String consentStatus,
        boolean purposeDeclared,
        boolean purposeApproved,
        ConsumerConsentPurpose requestedPurpose,
        String requestedDataScope,
        boolean dataScopeApproved,
        boolean tenantContextPresent,
        boolean consentProviderConfigured,
        boolean consentSourceTrusted,
        boolean humanReviewCompleted) {

    public static final String STATUS_UNIMPLEMENTED = "UNIMPLEMENTED";

    public ConsumerConsentContext {
        consentStatus = blankToEmpty(consentStatus);
        requestedPurpose = requestedPurpose == null ? ConsumerConsentPurpose.UNKNOWN : requestedPurpose;
        requestedDataScope = blankToEmpty(requestedDataScope);
    }

    /**
     * Laboratory context. It shows that a synthetic consent envelope exists
     * without claiming a verified consent, approved purpose, or real provider.
     * A declared conceptual purpose and abstract data scope are not approvals.
     */
    public static ConsumerConsentContext laboratory() {
        return new ConsumerConsentContext(
                true,
                false,
                false,
                STATUS_UNIMPLEMENTED,
                true,
                false,
                ConsumerConsentPurpose.FOLLOW_UP_SUPPORT,
                ConsumerConsentDataScopes.SUMMARY_METADATA,
                false,
                true,
                false,
                false,
                true);
    }

    public ConsumerConsentContext withContextPresent(boolean value) {
        return copy(
                value,
                consentReferencePresent,
                consentVerified,
                consentStatus,
                purposeDeclared,
                purposeApproved,
                requestedPurpose,
                requestedDataScope,
                dataScopeApproved,
                tenantContextPresent,
                consentProviderConfigured,
                consentSourceTrusted,
                humanReviewCompleted);
    }

    public ConsumerConsentContext withConsentReferencePresent(boolean value) {
        return copy(
                contextPresent,
                value,
                consentVerified,
                consentStatus,
                purposeDeclared,
                purposeApproved,
                requestedPurpose,
                requestedDataScope,
                dataScopeApproved,
                tenantContextPresent,
                consentProviderConfigured,
                consentSourceTrusted,
                humanReviewCompleted);
    }

    public ConsumerConsentContext withConsentVerified(boolean value) {
        return copy(
                contextPresent,
                consentReferencePresent,
                value,
                consentStatus,
                purposeDeclared,
                purposeApproved,
                requestedPurpose,
                requestedDataScope,
                dataScopeApproved,
                tenantContextPresent,
                consentProviderConfigured,
                consentSourceTrusted,
                humanReviewCompleted);
    }

    public ConsumerConsentContext withPurposeDeclared(boolean value) {
        return copy(
                contextPresent,
                consentReferencePresent,
                consentVerified,
                consentStatus,
                value,
                purposeApproved,
                requestedPurpose,
                requestedDataScope,
                dataScopeApproved,
                tenantContextPresent,
                consentProviderConfigured,
                consentSourceTrusted,
                humanReviewCompleted);
    }

    public ConsumerConsentContext withPurposeApproved(boolean value) {
        return copy(
                contextPresent,
                consentReferencePresent,
                consentVerified,
                consentStatus,
                purposeDeclared,
                value,
                requestedPurpose,
                requestedDataScope,
                dataScopeApproved,
                tenantContextPresent,
                consentProviderConfigured,
                consentSourceTrusted,
                humanReviewCompleted);
    }

    public ConsumerConsentContext withRequestedPurpose(ConsumerConsentPurpose value) {
        return copy(
                contextPresent,
                consentReferencePresent,
                consentVerified,
                consentStatus,
                purposeDeclared,
                purposeApproved,
                value,
                requestedDataScope,
                dataScopeApproved,
                tenantContextPresent,
                consentProviderConfigured,
                consentSourceTrusted,
                humanReviewCompleted);
    }

    public ConsumerConsentContext withRequestedDataScope(String value) {
        return copy(
                contextPresent,
                consentReferencePresent,
                consentVerified,
                consentStatus,
                purposeDeclared,
                purposeApproved,
                requestedPurpose,
                value,
                dataScopeApproved,
                tenantContextPresent,
                consentProviderConfigured,
                consentSourceTrusted,
                humanReviewCompleted);
    }

    public ConsumerConsentContext withDataScopeApproved(boolean value) {
        return copy(
                contextPresent,
                consentReferencePresent,
                consentVerified,
                consentStatus,
                purposeDeclared,
                purposeApproved,
                requestedPurpose,
                requestedDataScope,
                value,
                tenantContextPresent,
                consentProviderConfigured,
                consentSourceTrusted,
                humanReviewCompleted);
    }

    public ConsumerConsentContext withTenantContextPresent(boolean value) {
        return copy(
                contextPresent,
                consentReferencePresent,
                consentVerified,
                consentStatus,
                purposeDeclared,
                purposeApproved,
                requestedPurpose,
                requestedDataScope,
                dataScopeApproved,
                value,
                consentProviderConfigured,
                consentSourceTrusted,
                humanReviewCompleted);
    }

    public ConsumerConsentContext withHumanReviewCompleted(boolean value) {
        return copy(
                contextPresent,
                consentReferencePresent,
                consentVerified,
                consentStatus,
                purposeDeclared,
                purposeApproved,
                requestedPurpose,
                requestedDataScope,
                dataScopeApproved,
                tenantContextPresent,
                consentProviderConfigured,
                consentSourceTrusted,
                value);
    }

    private ConsumerConsentContext copy(
            boolean contextPresent,
            boolean consentReferencePresent,
            boolean consentVerified,
            String consentStatus,
            boolean purposeDeclared,
            boolean purposeApproved,
            ConsumerConsentPurpose requestedPurpose,
            String requestedDataScope,
            boolean dataScopeApproved,
            boolean tenantContextPresent,
            boolean consentProviderConfigured,
            boolean consentSourceTrusted,
            boolean humanReviewCompleted) {
        return new ConsumerConsentContext(
                contextPresent,
                consentReferencePresent,
                consentVerified,
                consentStatus,
                purposeDeclared,
                purposeApproved,
                requestedPurpose,
                requestedDataScope,
                dataScopeApproved,
                tenantContextPresent,
                consentProviderConfigured,
                consentSourceTrusted,
                humanReviewCompleted);
    }

    private static String blankToEmpty(String value) {
        return value == null ? "" : value.trim();
    }
}

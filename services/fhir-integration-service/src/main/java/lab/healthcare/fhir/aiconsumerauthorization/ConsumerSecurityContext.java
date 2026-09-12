package lab.healthcare.fhir.aiconsumerauthorization;

/**
 * Synthetic, untrusted security metadata. Presence of a field is not
 * authentication and is not authorization. Never includes tokens, secrets,
 * Patient identifiers, or FHIR JSON.
 */
public record ConsumerSecurityContext(
        boolean contextPresent,
        String authenticationMechanism,
        boolean authenticationVerified,
        String consumerType,
        boolean consumerIdentifierPresent,
        boolean authorizationEvaluated,
        boolean authorizationGranted,
        String requestedOperation,
        String requestedScope,
        boolean tenantContextPresent,
        boolean credentialMaterialPresent,
        boolean realSecurityProviderConfigured) {

    public static final String MECHANISM_UNIMPLEMENTED = "UNIMPLEMENTED";
    public static final String EVALUATE_CONSUMER_AUTHORIZATION = "EVALUATE_CONSUMER_AUTHORIZATION";

    public ConsumerSecurityContext {
        authenticationMechanism = blankToEmpty(authenticationMechanism);
        consumerType = blankToEmpty(consumerType);
        requestedOperation = blankToEmpty(requestedOperation);
        requestedScope = blankToEmpty(requestedScope);
    }

    /**
     * Laboratory context. It demonstrates that a synthetic context exists
     * without claiming a verified identity, scope, or real provider.
     */
    public static ConsumerSecurityContext laboratory() {
        return new ConsumerSecurityContext(
                true,
                MECHANISM_UNIMPLEMENTED,
                false,
                "LAB",
                false,
                false,
                false,
                EVALUATE_CONSUMER_AUTHORIZATION,
                "",
                true,
                false,
                false);
    }

    public ConsumerSecurityContext withAuthenticationVerified(boolean value) {
        return new ConsumerSecurityContext(
                contextPresent,
                authenticationMechanism,
                value,
                consumerType,
                consumerIdentifierPresent,
                authorizationEvaluated,
                authorizationGranted,
                requestedOperation,
                requestedScope,
                tenantContextPresent,
                credentialMaterialPresent,
                realSecurityProviderConfigured);
    }

    public ConsumerSecurityContext withAuthorizationGranted(boolean value) {
        return new ConsumerSecurityContext(
                contextPresent,
                authenticationMechanism,
                authenticationVerified,
                consumerType,
                consumerIdentifierPresent,
                authorizationEvaluated,
                value,
                requestedOperation,
                requestedScope,
                tenantContextPresent,
                credentialMaterialPresent,
                realSecurityProviderConfigured);
    }

    public ConsumerSecurityContext withConsumerIdentifierPresent(boolean value) {
        return new ConsumerSecurityContext(
                contextPresent,
                authenticationMechanism,
                authenticationVerified,
                consumerType,
                value,
                authorizationEvaluated,
                authorizationGranted,
                requestedOperation,
                requestedScope,
                tenantContextPresent,
                credentialMaterialPresent,
                realSecurityProviderConfigured);
    }

    public ConsumerSecurityContext withRequestedScope(String value) {
        return new ConsumerSecurityContext(
                contextPresent,
                authenticationMechanism,
                authenticationVerified,
                consumerType,
                consumerIdentifierPresent,
                authorizationEvaluated,
                authorizationGranted,
                requestedOperation,
                value,
                tenantContextPresent,
                credentialMaterialPresent,
                realSecurityProviderConfigured);
    }

    public ConsumerSecurityContext withTenantContextPresent(boolean value) {
        return new ConsumerSecurityContext(
                contextPresent,
                authenticationMechanism,
                authenticationVerified,
                consumerType,
                consumerIdentifierPresent,
                authorizationEvaluated,
                authorizationGranted,
                requestedOperation,
                requestedScope,
                value,
                credentialMaterialPresent,
                realSecurityProviderConfigured);
    }

    public ConsumerSecurityContext withContextPresent(boolean value) {
        return new ConsumerSecurityContext(
                value,
                authenticationMechanism,
                authenticationVerified,
                consumerType,
                consumerIdentifierPresent,
                authorizationEvaluated,
                authorizationGranted,
                requestedOperation,
                requestedScope,
                tenantContextPresent,
                credentialMaterialPresent,
                realSecurityProviderConfigured);
    }

    private static String blankToEmpty(String value) {
        return value == null ? "" : value.trim();
    }
}

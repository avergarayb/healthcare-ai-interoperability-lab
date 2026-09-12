package lab.healthcare.fhir.aiconsumerpolicy;

/**
 * Synthetic laboratory consumer metadata. Not a real identity, token, or
 * tenant.
 */
public record AiConsumerIdentity(
        String consumerId,
        String consumerType,
        String requestedContractVersion,
        String requestedOperation,
        String requestedScope,
        boolean tenantContextPresent,
        boolean authenticated,
        boolean authorized) {

    public static AiConsumerIdentity laboratory() {
        return new AiConsumerIdentity(
                "lab-consumer",
                "LAB",
                "v1",
                AiConsumerPolicyOperations.READ_CONTRACT,
                AiConsumerPolicyScopes.CONTRACT_READ,
                true,
                true,
                true);
    }

    String normalizedId() {
        return trim(consumerId);
    }

    String normalizedType() {
        return trim(consumerType);
    }

    String normalizedVersion() {
        return trim(requestedContractVersion);
    }

    String normalizedOperation() {
        return trim(requestedOperation);
    }

    String normalizedScope() {
        return trim(requestedScope);
    }

    private static String trim(String value) {
        return value == null ? "" : value.trim();
    }
}

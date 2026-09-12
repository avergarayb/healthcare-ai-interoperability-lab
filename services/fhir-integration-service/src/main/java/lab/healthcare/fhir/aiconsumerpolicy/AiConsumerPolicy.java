package lab.healthcare.fhir.aiconsumerpolicy;

import lab.healthcare.fhir.aiconsumer.AiConsumerContract;
import lab.healthcare.fhir.aiconsumer.AiConsumerContractStatus;
import lab.healthcare.fhir.aiconsumer.AiConsumerContractVersion;
import lab.healthcare.fhir.aiconsumer.AiConsumerDispatchStatus;
import lab.healthcare.fhir.firstai.FirstAiProcessingStatus;

/**
 * Deterministic consumer policy. Validates synthetic consumer metadata against
 * an existing contract. Never authenticates for real, never dispatches, never
 * calls a model.
 *
 * <p>Obligatory human review is {@code contractStatus=REQUIRES_HUMAN_REVIEW}.
 * The boolean {@code requiresHumanReview=true} stays copied onto every result
 * and does not by itself block {@link AiConsumerPolicyDecision#ALLOWED_FOR_FUTURE_CONSUMPTION}.
 */
public final class AiConsumerPolicy {

    private AiConsumerPolicy() {
    }

    public static AiConsumerPolicyResult evaluate(AiConsumerPolicyInput input) {
        if (input == null || input.contract() == null || input.consumer() == null) {
            return rejected(null, null, AiConsumerPolicyReasonCodes.INVALID_POLICY_INPUT);
        }
        AiConsumerContract contract = input.contract();
        AiConsumerIdentity consumer = input.consumer();
        if (consumer.normalizedId().isBlank() || consumer.normalizedType().isBlank()) {
            return rejected(contract, consumer, AiConsumerPolicyReasonCodes.INVALID_POLICY_INPUT);
        }
        if (!consumer.authenticated()) {
            return rejected(contract, consumer, AiConsumerPolicyReasonCodes.CONSUMER_NOT_AUTHENTICATED);
        }
        if (!consumer.authorized()) {
            return rejected(contract, consumer, AiConsumerPolicyReasonCodes.CONSUMER_NOT_AUTHORIZED);
        }
        if (!AiConsumerPolicyScopes.CONTRACT_READ.equals(consumer.normalizedScope())) {
            return rejected(contract, consumer, AiConsumerPolicyReasonCodes.REQUIRED_SCOPE_MISSING);
        }
        if (!AiConsumerContractVersion.V1.equals(consumer.normalizedVersion())) {
            return rejected(contract, consumer, AiConsumerPolicyReasonCodes.CONTRACT_VERSION_NOT_SUPPORTED);
        }
        boolean dispatchRequested =
                AiConsumerPolicyOperations.DISPATCH_TO_AI_SERVICE.equals(consumer.normalizedOperation());
        if (!dispatchRequested && !AiConsumerPolicyOperations.READ_CONTRACT.equals(consumer.normalizedOperation())) {
            return rejected(contract, consumer, AiConsumerPolicyReasonCodes.OPERATION_NOT_ALLOWED);
        }
        if (!consumer.tenantContextPresent()) {
            return rejected(contract, consumer, AiConsumerPolicyReasonCodes.TENANT_CONTEXT_REQUIRED);
        }
        if (contract.contractStatus() == AiConsumerContractStatus.BLOCKED) {
            return rejected(contract, consumer, AiConsumerPolicyReasonCodes.CONTRACT_NOT_CONSUMABLE);
        }
        if (contract.contractStatus() == AiConsumerContractStatus.NOT_ELIGIBLE) {
            return rejected(contract, consumer, AiConsumerPolicyReasonCodes.CONTRACT_NOT_ELIGIBLE);
        }
        if (contract.modelCallAuthorized()) {
            return rejected(contract, consumer, AiConsumerPolicyReasonCodes.PREMATURE_MODEL_AUTHORIZATION);
        }
        if (dispatchRequested || contract.dispatchStatus() != AiConsumerDispatchStatus.NOT_DISPATCHED) {
            return rejected(contract, consumer, AiConsumerPolicyReasonCodes.DISPATCH_NOT_SUPPORTED);
        }
        if (contract.modelCalled() || contract.processingStatus() != FirstAiProcessingStatus.NOT_EXECUTED) {
            return rejected(contract, consumer, AiConsumerPolicyReasonCodes.INVALID_POLICY_INPUT);
        }
        if (contract.contractStatus() == AiConsumerContractStatus.REQUIRES_HUMAN_REVIEW) {
            return result(
                    AiConsumerPolicyDecision.HUMAN_REVIEW_REQUIRED,
                    AiConsumerPolicyReasonCodes.CONTRACT_REQUIRES_HUMAN_REVIEW,
                    contract,
                    consumer);
        }
        if (contract.contractStatus() == AiConsumerContractStatus.READY) {
            return result(
                    AiConsumerPolicyDecision.ALLOWED_FOR_FUTURE_CONSUMPTION,
                    AiConsumerPolicyReasonCodes.ALLOWED_FOR_FUTURE_CONSUMPTION,
                    contract,
                    consumer);
        }
        return rejected(contract, consumer, AiConsumerPolicyReasonCodes.INVALID_POLICY_INPUT);
    }

    private static AiConsumerPolicyResult rejected(
            AiConsumerContract contract, AiConsumerIdentity consumer, String reason) {
        return result(AiConsumerPolicyDecision.REJECTED, reason, contract, consumer);
    }

    private static AiConsumerPolicyResult result(
            AiConsumerPolicyDecision decision,
            String reason,
            AiConsumerContract contract,
            AiConsumerIdentity consumer) {
        return new AiConsumerPolicyResult(
                decision,
                reason,
                contract == null ? "" : contract.contractVersion(),
                consumer == null ? "" : consumer.normalizedType(),
                consumer == null ? "" : consumer.normalizedOperation(),
                consumer == null ? "" : consumer.normalizedScope(),
                false,
                false,
                FirstAiProcessingStatus.NOT_EXECUTED,
                AiConsumerDispatchStatus.NOT_DISPATCHED,
                true);
    }
}

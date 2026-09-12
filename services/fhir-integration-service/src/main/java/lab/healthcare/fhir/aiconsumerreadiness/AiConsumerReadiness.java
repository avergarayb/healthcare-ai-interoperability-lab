package lab.healthcare.fhir.aiconsumerreadiness;

import lab.healthcare.fhir.aiconsumer.AiConsumerContractVersion;
import lab.healthcare.fhir.aiconsumer.AiConsumerDispatchStatus;
import lab.healthcare.fhir.aiconsumerpolicy.AiConsumerPolicyDecision;
import lab.healthcare.fhir.aiconsumerpolicy.AiConsumerPolicyOperations;
import lab.healthcare.fhir.aiconsumerpolicy.AiConsumerPolicyResult;
import lab.healthcare.fhir.aiconsumerpolicy.AiConsumerPolicyScopes;
import lab.healthcare.fhir.firstai.FirstAiProcessingStatus;

/**
 * Deterministic readiness over a consumer-policy result. Ready for a future
 * handoff is not handoff authorization, not dispatch, and not model permission.
 */
public final class AiConsumerReadiness {

    private AiConsumerReadiness() {
    }

    public static AiConsumerReadinessResult evaluate(AiConsumerPolicyResult policy) {
        if (policy == null) {
            return missingPolicy();
        }
        return evaluate(AiConsumerReadinessInput.from(policy));
    }

    public static AiConsumerReadinessResult evaluate(AiConsumerReadinessInput input) {
        if (input == null || input.policyDecision() == null) {
            return missingPolicy();
        }
        if (input.policyDecision() == AiConsumerPolicyDecision.REJECTED) {
            return result(AiConsumerReadinessStatus.BLOCKED, AiConsumerReadinessReasonCodes.POLICY_REJECTED, input);
        }
        if (input.policyDecision() == AiConsumerPolicyDecision.HUMAN_REVIEW_REQUIRED) {
            return result(
                    AiConsumerReadinessStatus.HUMAN_REVIEW_REQUIRED,
                    AiConsumerReadinessReasonCodes.POLICY_REQUIRES_HUMAN_REVIEW,
                    input);
        }
        if (input.policyDecision() != AiConsumerPolicyDecision.ALLOWED_FOR_FUTURE_CONSUMPTION) {
            return missingPolicy();
        }
        if (!input.requiresHumanReview()) {
            return result(
                    AiConsumerReadinessStatus.HUMAN_REVIEW_REQUIRED,
                    AiConsumerReadinessReasonCodes.HUMAN_REVIEW_FLAG_MISSING,
                    input);
        }
        if (!AiConsumerContractVersion.V1.equals(normalized(input.contractVersion()))) {
            return result(
                    AiConsumerReadinessStatus.BLOCKED,
                    AiConsumerReadinessReasonCodes.CONTRACT_VERSION_NOT_SUPPORTED,
                    input);
        }
        if (!AiConsumerPolicyOperations.READ_CONTRACT.equals(normalized(input.requestedOperation()))) {
            return result(
                    AiConsumerReadinessStatus.BLOCKED,
                    AiConsumerReadinessReasonCodes.OPERATION_NOT_SUPPORTED_FOR_READINESS,
                    input);
        }
        if (!AiConsumerPolicyScopes.CONTRACT_READ.equals(normalized(input.requestedScope()))) {
            return result(
                    AiConsumerReadinessStatus.BLOCKED,
                    AiConsumerReadinessReasonCodes.SCOPE_NOT_SUPPORTED_FOR_READINESS,
                    input);
        }
        if (input.modelCallAuthorized()
                || input.modelCalled()
                || !FirstAiProcessingStatus.NOT_EXECUTED.name().equals(normalized(input.processingStatus()))
                || !AiConsumerDispatchStatus.NOT_DISPATCHED.name().equals(normalized(input.dispatchStatus()))) {
            return result(
                    AiConsumerReadinessStatus.BLOCKED,
                    AiConsumerReadinessReasonCodes.INCONSISTENT_EXECUTION_STATE,
                    input);
        }
        return result(
                AiConsumerReadinessStatus.READY_FOR_FUTURE_HANDOFF,
                AiConsumerReadinessReasonCodes.READY_FOR_FUTURE_HANDOFF,
                input);
    }

    private static AiConsumerReadinessResult missingPolicy() {
        return new AiConsumerReadinessResult(
                AiConsumerReadinessStatus.NOT_READY,
                AiConsumerReadinessReasonCodes.POLICY_RESULT_MISSING,
                null,
                "",
                "",
                "",
                "",
                false,
                false,
                FirstAiProcessingStatus.NOT_EXECUTED,
                AiConsumerDispatchStatus.NOT_DISPATCHED,
                true,
                false,
                false);
    }

    private static AiConsumerReadinessResult result(
            AiConsumerReadinessStatus status, String reason, AiConsumerReadinessInput input) {
        return new AiConsumerReadinessResult(
                status,
                reason,
                input.policyDecision(),
                input.contractVersion(),
                input.requestedOperation(),
                input.requestedScope(),
                input.consumerType(),
                false,
                false,
                FirstAiProcessingStatus.NOT_EXECUTED,
                AiConsumerDispatchStatus.NOT_DISPATCHED,
                true,
                false,
                false);
    }

    private static String normalized(String value) {
        return value == null ? "" : value.trim();
    }
}

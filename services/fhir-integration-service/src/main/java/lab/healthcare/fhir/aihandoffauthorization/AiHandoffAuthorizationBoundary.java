package lab.healthcare.fhir.aihandoffauthorization;

import lab.healthcare.fhir.aiconsumer.AiConsumerDispatchStatus;
import lab.healthcare.fhir.aiconsumerreadiness.AiConsumerReadinessResult;
import lab.healthcare.fhir.aiconsumerreadiness.AiConsumerReadinessStatus;
import lab.healthcare.fhir.firstai.FirstAiProcessingStatus;

/**
 * Deny-by-default handoff authorization boundary. Ready for a future handoff
 * is not authorization, not dispatch, and not model permission. Task 064
 * never produces an effective authorization.
 */
public final class AiHandoffAuthorizationBoundary {

    private AiHandoffAuthorizationBoundary() {
    }

    public static AiHandoffAuthorizationResult evaluate(AiConsumerReadinessResult readiness) {
        if (readiness == null) {
            return missingReadiness();
        }
        return evaluate(AiHandoffAuthorizationInput.from(readiness));
    }

    public static AiHandoffAuthorizationResult evaluate(AiHandoffAuthorizationInput input) {
        if (input == null || input.readinessStatus() == null) {
            return missingReadiness();
        }
        if (input.readinessStatus() == AiConsumerReadinessStatus.BLOCKED) {
            return result(
                    AiHandoffAuthorizationStatus.BLOCKED,
                    AiHandoffAuthorizationReasonCodes.READINESS_BLOCKED,
                    input);
        }
        if (input.readinessStatus() == AiConsumerReadinessStatus.HUMAN_REVIEW_REQUIRED) {
            return result(
                    AiHandoffAuthorizationStatus.HUMAN_REVIEW_REQUIRED,
                    AiHandoffAuthorizationReasonCodes.READINESS_REQUIRES_HUMAN_REVIEW,
                    input);
        }
        if (input.readinessStatus() == AiConsumerReadinessStatus.NOT_READY) {
            return result(
                    AiHandoffAuthorizationStatus.NOT_READY_FOR_AUTHORIZATION,
                    AiHandoffAuthorizationReasonCodes.READINESS_NOT_COMPLETE,
                    input);
        }
        if (input.readinessStatus() != AiConsumerReadinessStatus.READY_FOR_FUTURE_HANDOFF) {
            return missingReadiness();
        }
        if (!input.requiresHumanReview()) {
            return result(
                    AiHandoffAuthorizationStatus.HUMAN_REVIEW_REQUIRED,
                    AiHandoffAuthorizationReasonCodes.HUMAN_REVIEW_FLAG_MISSING,
                    input);
        }
        if (inconsistentExecution(input)) {
            return result(
                    AiHandoffAuthorizationStatus.BLOCKED,
                    AiHandoffAuthorizationReasonCodes.INCONSISTENT_EXECUTION_STATE,
                    input);
        }
        if (handoffScopeRequested(input)) {
            return result(
                    AiHandoffAuthorizationStatus.HANDOFF_NOT_AUTHORIZED,
                    AiHandoffAuthorizationReasonCodes.HANDOFF_SCOPE_NOT_GRANTED,
                    input);
        }
        return result(
                AiHandoffAuthorizationStatus.HANDOFF_NOT_AUTHORIZED,
                AiHandoffAuthorizationReasonCodes.REAL_AUTHORIZATION_NOT_IMPLEMENTED,
                input);
    }

    private static boolean inconsistentExecution(AiHandoffAuthorizationInput input) {
        return input.modelCallAuthorized()
                || input.modelCalled()
                || !FirstAiProcessingStatus.NOT_EXECUTED.name().equals(normalized(input.processingStatus()))
                || !AiConsumerDispatchStatus.NOT_DISPATCHED.name().equals(normalized(input.dispatchStatus()))
                || input.handoffAuthorized()
                || input.dispatchPerformed();
    }

    private static boolean handoffScopeRequested(AiHandoffAuthorizationInput input) {
        String scope = normalized(input.requestedHandoffScope());
        return !scope.isEmpty() || AiHandoffAuthorizationScopes.HANDOFF_REQUEST.equals(scope);
    }

    private static AiHandoffAuthorizationResult missingReadiness() {
        return new AiHandoffAuthorizationResult(
                AiHandoffAuthorizationStatus.NOT_READY_FOR_AUTHORIZATION,
                AiHandoffAuthorizationReasonCodes.READINESS_RESULT_MISSING,
                null,
                null,
                "",
                "",
                "",
                "",
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                FirstAiProcessingStatus.NOT_EXECUTED,
                AiConsumerDispatchStatus.NOT_DISPATCHED,
                true);
    }

    private static AiHandoffAuthorizationResult result(
            AiHandoffAuthorizationStatus status, String reason, AiHandoffAuthorizationInput input) {
        return new AiHandoffAuthorizationResult(
                status,
                reason,
                input.readinessStatus(),
                input.policyDecision(),
                input.contractVersion(),
                input.requestedOperation(),
                input.requestedScope(),
                input.consumerType(),
                input.consumerIdentityPresent(),
                input.consumerAuthenticated(),
                input.consumerAuthorized(),
                input.tenantContextPresent(),
                false,
                false,
                false,
                false,
                false,
                FirstAiProcessingStatus.NOT_EXECUTED,
                AiConsumerDispatchStatus.NOT_DISPATCHED,
                true);
    }

    private static String normalized(String value) {
        return value == null ? "" : value.trim();
    }
}

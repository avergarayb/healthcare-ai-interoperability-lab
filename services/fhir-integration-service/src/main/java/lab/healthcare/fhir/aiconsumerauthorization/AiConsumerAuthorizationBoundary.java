package lab.healthcare.fhir.aiconsumerauthorization;

import lab.healthcare.fhir.aihandoffauthorization.AiHandoffAuthorizationResult;

/**
 * Deny-by-default consumer authentication and authorization boundary.
 * A declared identity is not authentication. Authentication is not
 * authorization. Authorization is not handoff. Task 065 never grants any
 * of those.
 */
public final class AiConsumerAuthorizationBoundary {

    private AiConsumerAuthorizationBoundary() {
    }

    public static AiConsumerAuthorizationResult evaluate(AiHandoffAuthorizationResult handoff) {
        if (handoff == null) {
            return missingHandoff();
        }
        return evaluate(AiConsumerAuthorizationInput.from(handoff));
    }

    public static AiConsumerAuthorizationResult evaluate(
            AiHandoffAuthorizationResult handoff, ConsumerSecurityContext security) {
        if (handoff == null) {
            return missingHandoff();
        }
        return evaluate(AiConsumerAuthorizationInput.of(handoff, security));
    }

    public static AiConsumerAuthorizationResult evaluate(AiConsumerAuthorizationInput input) {
        if (input == null || !input.handoffResultPresent()) {
            return missingHandoff();
        }
        ConsumerSecurityContext security =
                input.security() == null ? ConsumerSecurityContext.laboratory() : input.security();
        if (input.handoffAuthorized()) {
            return result(
                    AiConsumerAuthorizationStatus.BLOCKED,
                    AiConsumerAuthorizationReasonCodes.UNEXPECTED_HANDOFF_AUTHORIZATION,
                    security);
        }
        if (!input.requiresHumanReview()) {
            return result(
                    AiConsumerAuthorizationStatus.HUMAN_REVIEW_REQUIRED,
                    AiConsumerAuthorizationReasonCodes.HUMAN_REVIEW_FLAG_MISSING,
                    security);
        }
        if (security.authenticationVerified() && !security.realSecurityProviderConfigured()) {
            return result(
                    AiConsumerAuthorizationStatus.BLOCKED,
                    AiConsumerAuthorizationReasonCodes.UNTRUSTED_AUTHENTICATION_ASSERTION,
                    security);
        }
        if (security.authorizationGranted() && !security.realSecurityProviderConfigured()) {
            return result(
                    AiConsumerAuthorizationStatus.BLOCKED,
                    AiConsumerAuthorizationReasonCodes.UNTRUSTED_AUTHORIZATION_ASSERTION,
                    security);
        }
        if (!security.tenantContextPresent()) {
            return result(
                    AiConsumerAuthorizationStatus.BLOCKED,
                    AiConsumerAuthorizationReasonCodes.MISSING_TENANT_CONTEXT,
                    security);
        }
        if (security.consumerIdentifierPresent()) {
            return result(
                    AiConsumerAuthorizationStatus.NOT_AUTHENTICATED,
                    AiConsumerAuthorizationReasonCodes.CONSUMER_IDENTITY_NOT_VERIFIED,
                    security);
        }
        if (!normalized(security.requestedScope()).isEmpty()) {
            return result(
                    AiConsumerAuthorizationStatus.NOT_AUTHORIZED,
                    AiConsumerAuthorizationReasonCodes.SCOPE_NOT_VERIFIED,
                    security);
        }
        if (security.contextPresent()
                && !security.realSecurityProviderConfigured()
                && !security.authenticationVerified()
                && !security.authorizationEvaluated()) {
            return result(
                    AiConsumerAuthorizationStatus.AUTHORIZATION_NOT_IMPLEMENTED,
                    AiConsumerAuthorizationReasonCodes.REAL_AUTHENTICATION_AUTHORIZATION_NOT_IMPLEMENTED,
                    security);
        }
        return result(
                AiConsumerAuthorizationStatus.AUTHORIZATION_NOT_IMPLEMENTED,
                AiConsumerAuthorizationReasonCodes.HANDOFF_NOT_AUTHORIZED,
                security);
    }

    private static AiConsumerAuthorizationResult missingHandoff() {
        return result(
                AiConsumerAuthorizationStatus.BLOCKED,
                AiConsumerAuthorizationReasonCodes.MISSING_HANDOFF_AUTHORIZATION_RESULT,
                ConsumerSecurityContext.laboratory());
    }

    private static AiConsumerAuthorizationResult result(
            AiConsumerAuthorizationStatus status, String reason, ConsumerSecurityContext security) {
        return new AiConsumerAuthorizationResult(
                status,
                reason,
                security.requestedOperation(),
                security.requestedScope(),
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                AiConsumerAuthorizationResult.NOT_EXECUTED,
                AiConsumerAuthorizationResult.NOT_DISPATCHED,
                true);
    }

    private static String normalized(String value) {
        return value == null ? "" : value.trim();
    }
}

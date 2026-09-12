package lab.healthcare.fhir.aiconsumerscope;

import lab.healthcare.fhir.aiconsumerconsent.AiConsumerConsentResult;

import java.util.List;

/**
 * Deny-by-default clinical data-scope and minimization boundary.
 * A declared scope is not an evaluated scope. Minimization is not
 * clinical access. Task 067 never grants any of those.
 */
public final class AiConsumerDataScopeBoundary {

    private AiConsumerDataScopeBoundary() {
    }

    public static AiConsumerDataScopeResult evaluate(AiConsumerConsentResult consent) {
        if (consent == null) {
            return missingConsent();
        }
        return evaluate(AiConsumerDataScopeInput.from(consent));
    }

    public static AiConsumerDataScopeResult evaluate(
            AiConsumerConsentResult consent, ConsumerDataScopeContext scope) {
        if (consent == null) {
            return missingConsent();
        }
        return evaluate(AiConsumerDataScopeInput.of(consent, scope));
    }

    public static AiConsumerDataScopeResult evaluate(AiConsumerDataScopeInput input) {
        if (input == null || !input.consentResultPresent()) {
            return missingConsent();
        }
        ConsumerDataScopeContext scope =
                input.scope() == null ? ConsumerDataScopeContext.laboratory() : input.scope();
        if (untrustedAssertion(input, scope)) {
            return result(
                    AiConsumerDataScopeStatus.SCOPE_BLOCKED,
                    AiConsumerDataScopeReasonCodes.UNTRUSTED_SCOPE_ASSERTION,
                    input,
                    scope);
        }
        if (scope.contextPresent() && !scope.tenantScopePresent()) {
            return result(
                    AiConsumerDataScopeStatus.SCOPE_BLOCKED,
                    AiConsumerDataScopeReasonCodes.MISSING_TENANT_SCOPE,
                    input,
                    scope);
        }
        if (scope.hasDeclaredScope()) {
            return result(
                    AiConsumerDataScopeStatus.DATA_SCOPE_DECLARED_NOT_EVALUATED,
                    AiConsumerDataScopeReasonCodes.DATA_SCOPE_DECLARED_NOT_EVALUATED,
                    input,
                    scope);
        }
        if (scope.declarationAttempted()) {
            return result(
                    AiConsumerDataScopeStatus.DATA_SCOPE_NOT_DECLARED,
                    AiConsumerDataScopeReasonCodes.DATA_SCOPE_NOT_DECLARED,
                    input,
                    scope);
        }
        if (!input.consentAvailable() && !input.consentVerified()) {
            return result(
                    AiConsumerDataScopeStatus.NOT_READY_FOR_CLINICAL_DATA_ACCESS,
                    AiConsumerDataScopeReasonCodes.CONSENT_NOT_AVAILABLE,
                    input,
                    scope);
        }
        if (!input.purposeApproved()) {
            return result(
                    AiConsumerDataScopeStatus.PURPOSE_SCOPE_ALIGNMENT_NOT_VERIFIED,
                    AiConsumerDataScopeReasonCodes.PURPOSE_NOT_VERIFIED,
                    input,
                    scope);
        }
        return result(
                AiConsumerDataScopeStatus.NOT_READY_FOR_CLINICAL_DATA_ACCESS,
                AiConsumerDataScopeReasonCodes.NOT_READY_FOR_CLINICAL_DATA_ACCESS,
                input,
                scope);
    }

    private static boolean untrustedAssertion(AiConsumerDataScopeInput input, ConsumerDataScopeContext scope) {
        return input.consentAvailable()
                || input.consentVerified()
                || input.purposeApproved()
                || input.dataScopeApproved()
                || input.clinicalDataAccessAllowed()
                || scope.scopeEvaluatedClaim()
                || scope.minimizationEvaluatedClaim()
                || scope.purposeScopeAlignmentEvaluatedClaim()
                || scope.clinicalDataScopeProviderConfigured()
                || scope.clinicalDataScopeApprovalAvailable()
                || scope.clinicalDataAccessRequested()
                || scope.clinicalDataAccessGranted()
                || scope.clinicalDataAccessAllowedClaim();
    }

    private static AiConsumerDataScopeResult missingConsent() {
        return result(
                AiConsumerDataScopeStatus.SCOPE_BLOCKED,
                AiConsumerDataScopeReasonCodes.MISSING_CONSENT_RESULT,
                null,
                ConsumerDataScopeContext.laboratory());
    }

    private static AiConsumerDataScopeResult result(
            AiConsumerDataScopeStatus status,
            String reason,
            AiConsumerDataScopeInput input,
            ConsumerDataScopeContext scope) {
        boolean declared = scope.hasDeclaredScope();
        PurposeScopeAlignmentStatus alignment = alignment(input, declared);
        return new AiConsumerDataScopeResult(
                AiConsumerDataScopeResult.VERSION_V1,
                status,
                reason,
                AiConsumerDataScopeOperations.EVALUATE_CLINICAL_DATA_SCOPE,
                input != null && input.consentResultPresent(),
                declared
                        ? ConsumerDataScopeContext.SOURCE_SYNTHETIC_DECLARATION
                        : ConsumerDataScopeContext.SOURCE_LABORATORY,
                categories(scope),
                scope.declaredResourceTypes(),
                scope.declaredTenantScope(),
                declared,
                false,
                false,
                false,
                AiConsumerDataScopeResult.MINIMIZATION_NOT_EVALUATED,
                alignment,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                AiConsumerDataScopeResult.NOT_EXECUTED,
                AiConsumerDataScopeResult.NOT_DISPATCHED,
                true);
    }

    private static PurposeScopeAlignmentStatus alignment(AiConsumerDataScopeInput input, boolean declared) {
        boolean purposeDeclared = input != null
                && input.requestedPurpose() != null
                && !input.requestedPurpose().isBlank();
        if (!purposeDeclared || !declared) {
            return PurposeScopeAlignmentStatus.NOT_DECLARED;
        }
        return PurposeScopeAlignmentStatus.DECLARED_NOT_VERIFIED;
    }

    private static List<String> categories(ConsumerDataScopeContext scope) {
        return scope.declaredDataCategories().stream().map(Enum::name).toList();
    }
}

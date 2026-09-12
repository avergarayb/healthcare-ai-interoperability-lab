package lab.healthcare.fhir.aiconsumerenforcement;

import lab.healthcare.fhir.aiconsumeraccess.AiConsumerClinicalDataAccessResult;

/**
 * Deny-by-default clinical data-access enforcement boundary.
 * A pending request is not an access decision. A synthetic claim is
 * not enforcement. Task 069 never reads FHIR.
 */
public final class AiConsumerClinicalDataEnforcementBoundary {

    private AiConsumerClinicalDataEnforcementBoundary() {
    }

    public static AiConsumerClinicalDataEnforcementResult evaluate(AiConsumerClinicalDataAccessResult access) {
        if (access == null) {
            return missingAccess();
        }
        return evaluate(AiConsumerClinicalDataEnforcementInput.from(access));
    }

    public static AiConsumerClinicalDataEnforcementResult evaluate(
            AiConsumerClinicalDataAccessResult access, ClinicalDataEnforcementContext enforcement) {
        if (access == null) {
            return missingAccess();
        }
        return evaluate(AiConsumerClinicalDataEnforcementInput.of(access, enforcement));
    }

    public static AiConsumerClinicalDataEnforcementResult evaluate(AiConsumerClinicalDataEnforcementInput input) {
        if (input == null || !input.accessResultPresent()) {
            return missingAccess();
        }
        ClinicalDataEnforcementContext enforcement =
                input.enforcement() == null ? ClinicalDataEnforcementContext.laboratory() : input.enforcement();
        if (untrustedAssertion(input, enforcement)) {
            return result(
                    AiConsumerClinicalDataEnforcementStatus.ENFORCEMENT_BLOCKED,
                    AiConsumerClinicalDataEnforcementReasonCodes.UNTRUSTED_ENFORCEMENT_ASSERTION,
                    input,
                    enforcement);
        }
        if (enforcement.contextPresent() && !enforcement.tenantScopePresent()) {
            return result(
                    AiConsumerClinicalDataEnforcementStatus.ENFORCEMENT_BLOCKED,
                    AiConsumerClinicalDataEnforcementReasonCodes.MISSING_TENANT_SCOPE,
                    input,
                    enforcement);
        }
        boolean requestPending = input.accessRequestDeclared()
                || input.clinicalDataAccessRequested()
                || enforcement.requestReferencePresent();
        if (requestPending) {
            return result(
                    AiConsumerClinicalDataEnforcementStatus.ENFORCEMENT_REQUIRES_ACCESS_DECISION,
                    AiConsumerClinicalDataEnforcementReasonCodes.ENFORCEMENT_REQUIRES_ACCESS_DECISION,
                    input,
                    enforcement);
        }
        if (enforcement.authorizationEvaluationAttempted()
                || enforcement.authorizationDecisionReferencePresent()) {
            return result(
                    AiConsumerClinicalDataEnforcementStatus.ENFORCEMENT_REQUIRES_REAL_AUTHORIZATION,
                    AiConsumerClinicalDataEnforcementReasonCodes.ENFORCEMENT_REQUIRES_REAL_AUTHORIZATION,
                    input,
                    enforcement);
        }
        return result(
                AiConsumerClinicalDataEnforcementStatus.NOT_ENFORCED_FOR_CLINICAL_DATA_ACCESS,
                AiConsumerClinicalDataEnforcementReasonCodes.ACCESS_NOT_GRANTED,
                input,
                enforcement);
    }

    private static boolean untrustedAssertion(
            AiConsumerClinicalDataEnforcementInput input, ClinicalDataEnforcementContext enforcement) {
        return input.clinicalDataAccessGranted()
                || input.clinicalDataAccessAllowed()
                || input.clinicalDataAccessEnforced()
                || enforcement.enforcementDecisionAvailableClaim()
                || enforcement.enforcementDecisionEvaluatedClaim()
                || enforcement.clinicalDataAccessGrantedClaim()
                || enforcement.clinicalDataAccessAllowedClaim()
                || enforcement.clinicalDataAccessEnforcedClaim()
                || enforcement.clinicalDataAccessEnforcementAvailableClaim()
                || enforcement.clinicalDataAccessEnforcementProviderConfigured()
                || enforcement.clinicalDataAccessEnforcementExecutedClaim();
    }

    private static AiConsumerClinicalDataEnforcementResult missingAccess() {
        return result(
                AiConsumerClinicalDataEnforcementStatus.ENFORCEMENT_INPUT_NOT_AVAILABLE,
                AiConsumerClinicalDataEnforcementReasonCodes.MISSING_ACCESS_RESULT,
                null,
                ClinicalDataEnforcementContext.laboratory());
    }

    private static AiConsumerClinicalDataEnforcementResult result(
            AiConsumerClinicalDataEnforcementStatus status,
            String reason,
            AiConsumerClinicalDataEnforcementInput input,
            ClinicalDataEnforcementContext enforcement) {
        boolean requestReference = (input != null
                        && (input.accessRequestDeclared() || input.clinicalDataAccessRequested()))
                || enforcement.requestReferencePresent();
        boolean authorizationReference = enforcement.authorizationDecisionReferencePresent()
                || enforcement.authorizationEvaluationAttempted();
        boolean synthetic = requestReference || authorizationReference;
        return AiConsumerClinicalDataEnforcementResult.denied(
                status,
                reason,
                input != null && input.accessResultPresent(),
                synthetic
                        ? ClinicalDataEnforcementContext.SOURCE_SYNTHETIC_ENFORCEMENT
                        : ClinicalDataEnforcementContext.SOURCE_LABORATORY,
                requestReference,
                authorizationReference);
    }
}

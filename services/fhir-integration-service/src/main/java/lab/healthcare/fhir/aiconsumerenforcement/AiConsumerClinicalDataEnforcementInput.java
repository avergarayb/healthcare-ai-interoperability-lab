package lab.healthcare.fhir.aiconsumerenforcement;

import lab.healthcare.fhir.aiconsumeraccess.AiConsumerClinicalDataAccessResult;

/**
 * Enforcement input copied from an access-request result plus a
 * synthetic context. Unlike the 068 result, this record may hold
 * {@code clinicalDataAccessGranted=true} so the boundary can detect
 * that flag instead of silently accepting it.
 */
public record AiConsumerClinicalDataEnforcementInput(
        boolean accessResultPresent,
        boolean accessRequestDeclared,
        boolean clinicalDataAccessRequested,
        boolean clinicalDataAccessGranted,
        boolean clinicalDataAccessAllowed,
        boolean clinicalDataAccessEnforced,
        boolean realAuthorizationRequired,
        boolean requiresHumanReview,
        ClinicalDataEnforcementContext enforcement) {

    public static AiConsumerClinicalDataEnforcementInput from(AiConsumerClinicalDataAccessResult access) {
        if (access == null) {
            return null;
        }
        return new AiConsumerClinicalDataEnforcementInput(
                true,
                access.accessRequestDeclared(),
                access.clinicalDataAccessRequested(),
                access.clinicalDataAccessGranted(),
                access.clinicalDataAccessAllowed(),
                access.clinicalDataAccessEnforced(),
                access.realAuthorizationRequired(),
                access.requiresHumanReview(),
                ClinicalDataEnforcementContext.laboratory());
    }

    public static AiConsumerClinicalDataEnforcementInput of(
            AiConsumerClinicalDataAccessResult access, ClinicalDataEnforcementContext enforcement) {
        if (access == null) {
            return null;
        }
        return new AiConsumerClinicalDataEnforcementInput(
                true,
                access.accessRequestDeclared(),
                access.clinicalDataAccessRequested(),
                access.clinicalDataAccessGranted(),
                access.clinicalDataAccessAllowed(),
                access.clinicalDataAccessEnforced(),
                access.realAuthorizationRequired(),
                access.requiresHumanReview(),
                enforcement == null ? ClinicalDataEnforcementContext.laboratory() : enforcement);
    }

    public AiConsumerClinicalDataEnforcementInput withClinicalDataAccessGranted(boolean value) {
        return new AiConsumerClinicalDataEnforcementInput(
                accessResultPresent,
                accessRequestDeclared,
                clinicalDataAccessRequested,
                value,
                clinicalDataAccessAllowed,
                clinicalDataAccessEnforced,
                realAuthorizationRequired,
                requiresHumanReview,
                enforcement);
    }
}

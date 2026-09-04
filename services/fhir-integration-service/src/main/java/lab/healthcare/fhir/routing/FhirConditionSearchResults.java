package lab.healthcare.fhir.routing;

import lab.healthcare.fhir.capability.FhirCapabilityException;
import lab.healthcare.fhir.exception.FhirClientException;
import lab.healthcare.fhir.exception.FhirErrorCategory;
import lab.healthcare.fhir.exception.FhirErrorClassifier;
import lab.healthcare.fhir.exception.FhirErrorDetails;
import lab.healthcare.fhir.patient.PatientContextSource;

import org.hl7.fhir.r4.model.Bundle;

/**
 * Maps transport and FHIR failures onto {@link FhirConditionSearchResult}
 * without copying tokens or clinical payloads.
 */
public final class FhirConditionSearchResults {

    private FhirConditionSearchResults() {
    }

    public static FhirConditionSearchResult succeeded(String destination, Bundle bundle) {
        String responseType = bundle == null ? "" : bundle.fhirType();
        boolean hasEntries = bundle != null && bundle.hasEntry();
        return new FhirConditionSearchResult(
                FhirConditionSearchOutcome.CONDITION_SEARCH_SUCCEEDED,
                destination,
                "Condition",
                responseType,
                200,
                null,
                PatientContextSource.CONFIGURED,
                true,
                hasEntries,
                "Authenticated Condition search succeeded");
    }

    public static FhirConditionSearchResult fromFailure(String destination, RuntimeException ex) {
        FhirErrorDetails details = detailsOf(ex);
        if (details.category() == FhirErrorCategory.AUTHENTICATION_ERROR
                || Integer.valueOf(401).equals(details.status())) {
            return new FhirConditionSearchResult(
                    FhirConditionSearchOutcome.AUTHENTICATION_REJECTED,
                    destination,
                    "Condition",
                    "",
                    details.status() == null ? 401 : details.status(),
                    FhirErrorCategory.AUTHENTICATION_ERROR,
                    PatientContextSource.CONFIGURED,
                    true,
                    null,
                    FhirErrorCategory.AUTHENTICATION_ERROR.safeMessage());
        }
        if (details.category() == FhirErrorCategory.AUTHORIZATION_ERROR
                || Integer.valueOf(403).equals(details.status())) {
            return new FhirConditionSearchResult(
                    FhirConditionSearchOutcome.AUTHORIZATION_DENIED,
                    destination,
                    "Condition",
                    "",
                    details.status() == null ? 403 : details.status(),
                    FhirErrorCategory.AUTHORIZATION_ERROR,
                    PatientContextSource.CONFIGURED,
                    true,
                    null,
                    FhirErrorCategory.AUTHORIZATION_ERROR.safeMessage());
        }
        return new FhirConditionSearchResult(
                FhirConditionSearchOutcome.DEPENDENCY_FAILURE,
                destination,
                "Condition",
                "",
                details.status(),
                details.category(),
                PatientContextSource.CONFIGURED,
                true,
                null,
                details.category().safeMessage());
    }

    private static FhirErrorDetails detailsOf(RuntimeException ex) {
        if (ex instanceof FhirClientException fhir) {
            return fhir.details();
        }
        if (ex instanceof RoutingException routing) {
            return routing.details();
        }
        if (ex instanceof FhirCapabilityException) {
            return FhirErrorDetails.of(FhirErrorCategory.VALIDATION_ERROR, null, ex.getMessage());
        }
        return FhirErrorClassifier.classify(ex);
    }
}

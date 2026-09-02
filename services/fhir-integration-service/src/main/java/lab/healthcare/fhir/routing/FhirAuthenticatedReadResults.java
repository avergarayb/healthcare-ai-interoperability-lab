package lab.healthcare.fhir.routing;

import lab.healthcare.fhir.capability.FhirCapabilityException;
import lab.healthcare.fhir.exception.FhirClientException;
import lab.healthcare.fhir.exception.FhirErrorCategory;
import lab.healthcare.fhir.exception.FhirErrorClassifier;
import lab.healthcare.fhir.exception.FhirErrorDetails;

import org.hl7.fhir.r4.model.Bundle;

/**
 * Maps transport and FHIR failures onto {@link FhirAuthenticatedReadResult}
 * without copying tokens or clinical payloads.
 */
public final class FhirAuthenticatedReadResults {

    private FhirAuthenticatedReadResults() {
    }

    public static FhirAuthenticatedReadResult succeeded(String destination, Bundle bundle) {
        String responseType = bundle == null ? "" : bundle.fhirType();
        boolean hasEntries = bundle != null && bundle.hasEntry();
        return new FhirAuthenticatedReadResult(
                FhirAuthenticatedReadOutcome.AUTHENTICATED_READ_SUCCEEDED,
                destination,
                "Patient",
                responseType,
                200,
                null,
                hasEntries,
                "Authenticated Patient search succeeded");
    }

    public static FhirAuthenticatedReadResult fromFailure(String destination, RuntimeException ex) {
        FhirErrorDetails details = detailsOf(ex);
        if (details.category() == FhirErrorCategory.AUTHENTICATION_ERROR
                || Integer.valueOf(401).equals(details.status())) {
            return new FhirAuthenticatedReadResult(
                    FhirAuthenticatedReadOutcome.AUTHENTICATION_REJECTED,
                    destination,
                    "Patient",
                    "",
                    details.status() == null ? 401 : details.status(),
                    FhirErrorCategory.AUTHENTICATION_ERROR,
                    null,
                    FhirErrorCategory.AUTHENTICATION_ERROR.safeMessage());
        }
        if (details.category() == FhirErrorCategory.AUTHORIZATION_ERROR
                || Integer.valueOf(403).equals(details.status())) {
            return new FhirAuthenticatedReadResult(
                    FhirAuthenticatedReadOutcome.AUTHORIZATION_DENIED,
                    destination,
                    "Patient",
                    "",
                    details.status() == null ? 403 : details.status(),
                    FhirErrorCategory.AUTHORIZATION_ERROR,
                    null,
                    FhirErrorCategory.AUTHORIZATION_ERROR.safeMessage());
        }
        return new FhirAuthenticatedReadResult(
                FhirAuthenticatedReadOutcome.DEPENDENCY_FAILURE,
                destination,
                "Patient",
                "",
                details.status(),
                details.category(),
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

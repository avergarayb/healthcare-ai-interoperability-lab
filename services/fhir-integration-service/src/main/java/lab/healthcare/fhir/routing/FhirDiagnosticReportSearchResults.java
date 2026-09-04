package lab.healthcare.fhir.routing;

import lab.healthcare.fhir.capability.FhirCapabilityException;
import lab.healthcare.fhir.exception.FhirClientException;
import lab.healthcare.fhir.exception.FhirErrorCategory;
import lab.healthcare.fhir.exception.FhirErrorClassifier;
import lab.healthcare.fhir.exception.FhirErrorDetails;
import lab.healthcare.fhir.patient.PatientContextSource;

import org.hl7.fhir.r4.model.Bundle;

/**
 * Maps transport and FHIR failures onto {@link FhirDiagnosticReportSearchResult}
 * without copying tokens or clinical payloads.
 */
public final class FhirDiagnosticReportSearchResults {

    private FhirDiagnosticReportSearchResults() {
    }

    public static FhirDiagnosticReportSearchResult succeeded(String destination, Bundle bundle) {
        String responseType = bundle == null ? "" : bundle.fhirType();
        boolean hasEntries = bundle != null && bundle.hasEntry();
        return new FhirDiagnosticReportSearchResult(
                FhirDiagnosticReportSearchOutcome.DIAGNOSTIC_REPORT_SEARCH_SUCCEEDED,
                destination,
                "DiagnosticReport",
                responseType,
                200,
                null,
                PatientContextSource.CONFIGURED,
                true,
                hasEntries,
                "Authenticated DiagnosticReport search succeeded");
    }

    public static FhirDiagnosticReportSearchResult fromFailure(String destination, RuntimeException ex) {
        FhirErrorDetails details = detailsOf(ex);
        if (details.category() == FhirErrorCategory.AUTHENTICATION_ERROR
                || Integer.valueOf(401).equals(details.status())) {
            return new FhirDiagnosticReportSearchResult(
                    FhirDiagnosticReportSearchOutcome.AUTHENTICATION_REJECTED,
                    destination,
                    "DiagnosticReport",
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
            return new FhirDiagnosticReportSearchResult(
                    FhirDiagnosticReportSearchOutcome.AUTHORIZATION_DENIED,
                    destination,
                    "DiagnosticReport",
                    "",
                    details.status() == null ? 403 : details.status(),
                    FhirErrorCategory.AUTHORIZATION_ERROR,
                    PatientContextSource.CONFIGURED,
                    true,
                    null,
                    FhirErrorCategory.AUTHORIZATION_ERROR.safeMessage());
        }
        return new FhirDiagnosticReportSearchResult(
                FhirDiagnosticReportSearchOutcome.DEPENDENCY_FAILURE,
                destination,
                "DiagnosticReport",
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

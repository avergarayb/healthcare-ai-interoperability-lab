package lab.healthcare.fhir.routing;

import lab.healthcare.fhir.capability.FhirCapabilityException;
import lab.healthcare.fhir.exception.FhirClientException;
import lab.healthcare.fhir.exception.FhirErrorCategory;
import lab.healthcare.fhir.exception.FhirErrorClassifier;
import lab.healthcare.fhir.exception.FhirErrorDetails;
import lab.healthcare.fhir.patient.PatientContextSource;

import org.hl7.fhir.r4.model.Patient;

/**
 * Maps transport and FHIR failures onto {@link FhirPatientReadResult} without
 * copying tokens or clinical payloads.
 */
public final class FhirPatientReadResults {

    private FhirPatientReadResults() {
    }

    public static FhirPatientReadResult succeeded(String destination, Patient patient) {
        String responseType = patient == null ? "" : patient.fhirType();
        return new FhirPatientReadResult(
                FhirPatientReadOutcome.PATIENT_READ_SUCCEEDED,
                destination,
                "Patient",
                responseType,
                200,
                null,
                PatientContextSource.CONFIGURED,
                true,
                "Authenticated Patient read succeeded");
    }

    public static FhirPatientReadResult fromFailure(String destination, RuntimeException ex) {
        FhirErrorDetails details = detailsOf(ex);
        if (details.category() == FhirErrorCategory.AUTHENTICATION_ERROR
                || Integer.valueOf(401).equals(details.status())) {
            return new FhirPatientReadResult(
                    FhirPatientReadOutcome.AUTHENTICATION_REJECTED,
                    destination,
                    "Patient",
                    "",
                    details.status() == null ? 401 : details.status(),
                    FhirErrorCategory.AUTHENTICATION_ERROR,
                    PatientContextSource.CONFIGURED,
                    true,
                    FhirErrorCategory.AUTHENTICATION_ERROR.safeMessage());
        }
        if (details.category() == FhirErrorCategory.AUTHORIZATION_ERROR
                || Integer.valueOf(403).equals(details.status())) {
            return new FhirPatientReadResult(
                    FhirPatientReadOutcome.AUTHORIZATION_DENIED,
                    destination,
                    "Patient",
                    "",
                    details.status() == null ? 403 : details.status(),
                    FhirErrorCategory.AUTHORIZATION_ERROR,
                    PatientContextSource.CONFIGURED,
                    true,
                    FhirErrorCategory.AUTHORIZATION_ERROR.safeMessage());
        }
        if (details.category() == FhirErrorCategory.NOT_FOUND || Integer.valueOf(404).equals(details.status())) {
            return new FhirPatientReadResult(
                    FhirPatientReadOutcome.PATIENT_NOT_FOUND,
                    destination,
                    "Patient",
                    "",
                    details.status() == null ? 404 : details.status(),
                    FhirErrorCategory.NOT_FOUND,
                    PatientContextSource.CONFIGURED,
                    true,
                    FhirErrorCategory.NOT_FOUND.safeMessage());
        }
        return new FhirPatientReadResult(
                FhirPatientReadOutcome.DEPENDENCY_FAILURE,
                destination,
                "Patient",
                "",
                details.status(),
                details.category(),
                PatientContextSource.CONFIGURED,
                true,
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

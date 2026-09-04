package lab.healthcare.fhir.snapshot;

import lab.healthcare.fhir.capability.FhirCapabilityException;
import lab.healthcare.fhir.exception.FhirClientException;
import lab.healthcare.fhir.exception.FhirErrorCategory;
import lab.healthcare.fhir.exception.FhirErrorClassifier;
import lab.healthcare.fhir.exception.FhirErrorDetails;
import lab.healthcare.fhir.routing.RoutingException;

/**
 * Maps transport and FHIR failures onto a resource status without copying
 * tokens or clinical payloads.
 */
public final class ClinicalSnapshotStatuses {

    private ClinicalSnapshotStatuses() {
    }

    public static ClinicalSnapshotResourceStatus fromFailure(RuntimeException ex) {
        FhirErrorDetails details = detailsOf(ex);
        if (details.category() == FhirErrorCategory.AUTHORIZATION_ERROR
                || Integer.valueOf(403).equals(details.status())) {
            return ClinicalSnapshotResourceStatus.UNAUTHORIZED;
        }
        return ClinicalSnapshotResourceStatus.FAILED;
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

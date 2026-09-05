package lab.healthcare.fhir.modelboundary;

import lab.healthcare.fhir.projection.ClinicalProjectionResult;
import lab.healthcare.fhir.projection.ProjectedCollection;
import lab.healthcare.fhir.projection.RetainedCondition;
import lab.healthcare.fhir.projection.RetainedDiagnosticReport;
import lab.healthcare.fhir.projection.RetainedMedicationRequest;
import lab.healthcare.fhir.projection.RetainedObservation;
import lab.healthcare.fhir.projection.RetainedPatient;

import java.util.List;
import java.util.function.Function;

/**
 * Copies only Task 042 allowlisted fields onto the v1 model boundary. Does not
 * fetch FHIR, enrich records, or invent vendor metadata.
 */
public final class ModelBoundaryMapper {

    private ModelBoundaryMapper() {
    }

    public static ModelBoundaryContract from(ClinicalProjectionResult projection) {
        if (projection == null) {
            throw new IllegalArgumentException("Clinical projection must be provided");
        }
        return new ModelBoundaryContract(
                ModelBoundaryContractVersion.V1,
                projection.destination(),
                projection.contextSource(),
                projection.generatedAt(),
                projection.outcome(),
                patient(projection),
                collection(projection.conditions(), ModelBoundaryMapper::condition),
                collection(projection.observations(), ModelBoundaryMapper::observation),
                collection(projection.diagnosticReports(), ModelBoundaryMapper::diagnosticReport),
                collection(projection.medicationRequests(), ModelBoundaryMapper::medicationRequest));
    }

    private static BoundaryPatient patient(ClinicalProjectionResult projection) {
        if (projection.patientStatus() == null && projection.patient() == null) {
            return null;
        }
        RetainedPatient retained = projection.patient();
        return new BoundaryPatient(
                projection.patientStatus(), retained == null ? "" : retained.resourceType());
    }

    private static <S, T> BoundaryCollection<T> collection(
            ProjectedCollection<S> source, Function<S, T> mapper) {
        if (source == null) {
            return null;
        }
        List<T> records = source.items() == null
                ? List.of()
                : source.items().stream().map(mapper).toList();
        return new BoundaryCollection<>(
                source.status(),
                source.receivedCount(),
                source.retainedCount(),
                source.truncated(),
                records);
    }

    private static BoundaryCondition condition(RetainedCondition condition) {
        return new BoundaryCondition(condition.resourceType(), condition.clinicalStatus());
    }

    private static BoundaryObservation observation(RetainedObservation observation) {
        return new BoundaryObservation(observation.resourceType(), observation.status());
    }

    private static BoundaryDiagnosticReport diagnosticReport(RetainedDiagnosticReport report) {
        return new BoundaryDiagnosticReport(report.resourceType(), report.status());
    }

    private static BoundaryMedicationRequest medicationRequest(RetainedMedicationRequest request) {
        return new BoundaryMedicationRequest(request.resourceType(), request.status(), request.intent());
    }
}

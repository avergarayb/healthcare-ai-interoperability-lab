package lab.healthcare.fhir.projection;

import org.hl7.fhir.r4.model.CodeableConcept;
import org.hl7.fhir.r4.model.Coding;
import org.hl7.fhir.r4.model.Condition;
import org.hl7.fhir.r4.model.DiagnosticReport;
import org.hl7.fhir.r4.model.MedicationRequest;
import org.hl7.fhir.r4.model.Observation;
import org.hl7.fhir.r4.model.Patient;
import org.hl7.fhir.r4.model.Resource;

/**
 * Copies only the Task 042 allowlist from HAPI resources. HAPI types stay inside
 * this mapper and do not become the public projection model.
 */
public final class ClinicalProjectionMapper {

    private ClinicalProjectionMapper() {
    }

    public static RetainedPatient patient(Patient patient) {
        return new RetainedPatient(resourceType(patient, "Patient"));
    }

    public static RetainedCondition condition(Resource resource) {
        if (!(resource instanceof Condition condition)) {
            return new RetainedCondition(resourceType(resource, "Condition"), "");
        }
        return new RetainedCondition("Condition", firstCode(condition.getClinicalStatus()));
    }

    public static RetainedObservation observation(Resource resource) {
        if (!(resource instanceof Observation observation)) {
            return new RetainedObservation(resourceType(resource, "Observation"), "");
        }
        return new RetainedObservation(
                "Observation", observation.hasStatus() ? observation.getStatus().toCode() : "");
    }

    public static RetainedDiagnosticReport diagnosticReport(Resource resource) {
        if (!(resource instanceof DiagnosticReport report)) {
            return new RetainedDiagnosticReport(resourceType(resource, "DiagnosticReport"), "");
        }
        return new RetainedDiagnosticReport(
                "DiagnosticReport", report.hasStatus() ? report.getStatus().toCode() : "");
    }

    public static RetainedMedicationRequest medicationRequest(Resource resource) {
        if (!(resource instanceof MedicationRequest request)) {
            return new RetainedMedicationRequest(resourceType(resource, "MedicationRequest"), "", "");
        }
        return new RetainedMedicationRequest(
                "MedicationRequest",
                request.hasStatus() ? request.getStatus().toCode() : "",
                request.hasIntent() ? request.getIntent().toCode() : "");
    }

    private static String resourceType(Resource resource, String fallback) {
        if (resource == null || resource.fhirType() == null || resource.fhirType().isBlank()) {
            return fallback;
        }
        return resource.fhirType();
    }

    private static String firstCode(CodeableConcept concept) {
        if (concept == null || !concept.hasCoding()) {
            return "";
        }
        Coding coding = concept.getCodingFirstRep();
        return coding.hasCode() ? coding.getCode() : "";
    }
}

package lab.healthcare.fhir.modelboundary;

/**
 * DiagnosticReport record that may cross the v1 model boundary. Never includes
 * text, conclusion, or attachments.
 */
public record BoundaryDiagnosticReport(String resourceType, String status) {

    public BoundaryDiagnosticReport {
        resourceType = resourceType == null ? "" : resourceType.trim();
        status = status == null ? "" : status.trim();
    }
}

package lab.healthcare.fhir.projection;

/**
 * Allowlisted DiagnosticReport projection. Never includes text, conclusion, or attachments.
 */
public record RetainedDiagnosticReport(String resourceType, String status) {

    public RetainedDiagnosticReport {
        resourceType = resourceType == null ? "" : resourceType.trim();
        status = status == null ? "" : status.trim();
    }
}

package lab.healthcare.fhir.aiboundary;

import lab.healthcare.fhir.pipeline.SafePipelineLog;

import java.util.List;

/**
 * Controlled payload a future ai-service may consider. Never includes record
 * values, tokens, Patient identifiers, or FHIR JSON.
 */
public record AiBoundaryResult(
        AiBoundaryDecision decision,
        String contractVersion,
        String destination,
        String reasonCode,
        List<String> warnings,
        String medicationRequestsStatus,
        boolean contractValid,
        boolean usable,
        String correlationId) {

    public AiBoundaryResult {
        if (decision == null) {
            throw new IllegalArgumentException("AI boundary decision must be provided");
        }
        contractVersion = SafePipelineLog.sanitize(contractVersion == null ? "" : contractVersion.trim());
        destination = SafePipelineLog.sanitize(destination == null ? "" : destination.trim());
        reasonCode = SafePipelineLog.sanitize(reasonCode == null ? "" : reasonCode.trim());
        medicationRequestsStatus =
                SafePipelineLog.sanitize(medicationRequestsStatus == null ? "" : medicationRequestsStatus.trim());
        correlationId = SafePipelineLog.sanitize(correlationId == null ? "" : correlationId.trim());
        warnings = sanitized(warnings);
    }

    @Override
    public String toString() {
        return "AiBoundaryResult[agentDecision="
                + decision.agentDecision()
                + ", pipelineStatus="
                + decision.pipelineStatus()
                + ", clinicalDataAvailable="
                + decision.clinicalDataAvailable()
                + ", requiresHumanReview="
                + decision.requiresHumanReview()
                + ", modelCalled="
                + decision.modelCalled()
                + ", modelCallAuthorized="
                + decision.modelCallAuthorized()
                + ", reasonCode="
                + reasonCode
                + ", warnings="
                + warnings.size()
                + ", medicationRequestsStatus="
                + medicationRequestsStatus
                + "]";
    }

    private static List<String> sanitized(List<String> values) {
        if (values == null || values.isEmpty()) {
            return List.of();
        }
        return values.stream()
                .map(value -> SafePipelineLog.sanitize(value == null ? "" : value.trim()))
                .filter(value -> !value.isBlank())
                .toList();
    }
}

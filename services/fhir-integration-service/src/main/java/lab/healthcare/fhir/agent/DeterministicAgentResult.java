package lab.healthcare.fhir.agent;

import lab.healthcare.fhir.pipeline.PipelineStageStatus;
import lab.healthcare.fhir.pipeline.SafePipelineLog;

import java.util.List;

/**
 * Structured deterministic verdict. {@link #toString()} never includes record
 * values, Patient identifiers, tokens, or model output.
 */
public record DeterministicAgentResult(
        AgentDecision decision,
        String reasonCode,
        List<String> findings,
        List<String> warnings,
        boolean requiresHumanReview,
        boolean modelCalled,
        PipelineStageStatus pipelineStatus,
        boolean contractValid,
        boolean usable) {

    public DeterministicAgentResult {
        if (decision == null) {
            throw new IllegalArgumentException("Agent decision must be provided");
        }
        if (reasonCode == null || reasonCode.isBlank()) {
            throw new IllegalArgumentException("Agent reason code must be provided");
        }
        if (pipelineStatus == null) {
            throw new IllegalArgumentException("Pipeline status must be provided");
        }
        if (modelCalled) {
            throw new IllegalArgumentException("Deterministic agent must not call a model");
        }
        reasonCode = SafePipelineLog.sanitize(reasonCode.trim());
        findings = sanitized(findings);
        warnings = sanitized(warnings);
    }

    @Override
    public String toString() {
        return "DeterministicAgentResult[decision="
                + decision
                + ", reasonCode="
                + reasonCode
                + ", findings="
                + findings.size()
                + ", warnings="
                + warnings.size()
                + ", requiresHumanReview="
                + requiresHumanReview
                + ", modelCalled="
                + modelCalled
                + ", pipelineStatus="
                + pipelineStatus
                + ", contractValid="
                + contractValid
                + ", usable="
                + usable
                + "]";
    }

    private static List<String> sanitized(List<String> values) {
        if (values == null || values.isEmpty()) {
            return List.of();
        }
        return values.stream().map(value -> SafePipelineLog.sanitize(value == null ? "" : value.trim()))
                .filter(value -> !value.isBlank())
                .toList();
    }
}

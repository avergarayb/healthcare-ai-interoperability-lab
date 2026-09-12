package lab.healthcare.fhir.aiboundary;

import lab.healthcare.fhir.agent.AgentDecision;
import lab.healthcare.fhir.pipeline.PipelineStageStatus;

/**
 * Separated frontier judgments. {@code READY} is not model authorization.
 */
public record AiBoundaryDecision(
        PipelineStageStatus pipelineStatus,
        boolean clinicalDataAvailable,
        AgentDecision agentDecision,
        boolean requiresHumanReview,
        boolean modelCalled,
        boolean modelCallAuthorized) {

    public AiBoundaryDecision {
        if (pipelineStatus == null) {
            throw new IllegalArgumentException("AI boundary pipeline status must be provided");
        }
        if (agentDecision == null) {
            throw new IllegalArgumentException("AI boundary agent decision must be provided");
        }
        if (modelCalled) {
            throw new IllegalArgumentException("AI boundary must not call a model");
        }
        if (modelCallAuthorized) {
            throw new IllegalArgumentException("READY does not authorize a model call");
        }
        if (!requiresHumanReview) {
            throw new IllegalArgumentException("AI boundary requires human review");
        }
    }
}

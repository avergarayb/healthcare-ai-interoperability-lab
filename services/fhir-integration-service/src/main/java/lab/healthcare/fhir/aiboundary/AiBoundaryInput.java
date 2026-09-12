package lab.healthcare.fhir.aiboundary;

import lab.healthcare.fhir.agent.DeterministicAgentResult;
import lab.healthcare.fhir.modelboundary.ModelBoundaryContract;
import lab.healthcare.fhir.pipeline.PipelineDiagnosis;

/**
 * Authorized input to the AI boundary. Does not contain FHIR resources, vendor
 * DTOs, tokens, or infrastructure clients.
 */
public record AiBoundaryInput(
        ModelBoundaryContract contract, PipelineDiagnosis diagnosis, DeterministicAgentResult agent) {

    public AiBoundaryInput {
        if (contract == null) {
            throw new IllegalArgumentException("AI boundary requires a model boundary contract");
        }
        if (agent == null) {
            throw new IllegalArgumentException("AI boundary requires a deterministic agent result");
        }
    }

    public static AiBoundaryInput of(
            ModelBoundaryContract contract, PipelineDiagnosis diagnosis, DeterministicAgentResult agent) {
        return new AiBoundaryInput(contract, diagnosis, agent);
    }
}

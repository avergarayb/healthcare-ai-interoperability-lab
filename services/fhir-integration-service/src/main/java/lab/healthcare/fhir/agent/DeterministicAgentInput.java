package lab.healthcare.fhir.agent;

import lab.healthcare.fhir.modelboundary.ModelBoundaryContract;
import lab.healthcare.fhir.pipeline.PipelineDiagnosis;

/**
 * Authorized agent input. The contract is required. A diagnosis may be
 * supplied or derived later from the contract.
 */
public record DeterministicAgentInput(ModelBoundaryContract contract, PipelineDiagnosis diagnosis) {

    public DeterministicAgentInput {
        if (contract == null) {
            throw new AgentValidationException("Deterministic agent requires a model boundary contract");
        }
    }

    public static DeterministicAgentInput of(ModelBoundaryContract contract) {
        return new DeterministicAgentInput(contract, null);
    }

    public static DeterministicAgentInput of(ModelBoundaryContract contract, PipelineDiagnosis diagnosis) {
        return new DeterministicAgentInput(contract, diagnosis);
    }
}

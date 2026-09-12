package lab.healthcare.fhir.aiboundary;

import lab.healthcare.fhir.agent.AgentDecision;
import lab.healthcare.fhir.agent.AgentReasonCodes;
import lab.healthcare.fhir.agent.DeterministicAgentResult;
import lab.healthcare.fhir.pipeline.PipelineDiagnosis;
import lab.healthcare.fhir.pipeline.PipelineStageDiagnosis;
import lab.healthcare.fhir.pipeline.PipelineStageStatus;

/**
 * Copies authorized 057 output onto the AI boundary. Does not re-evaluate
 * READY/BLOCKED rules or fetch FHIR.
 */
public final class AiBoundaryMapper {

    private AiBoundaryMapper() {
    }

    public static AiBoundaryResult from(AiBoundaryInput input, String correlationId) {
        if (input == null) {
            throw new IllegalArgumentException("AI boundary input must be provided");
        }
        DeterministicAgentResult agent = input.agent();
        PipelineDiagnosis diagnosis = input.diagnosis();
        return new AiBoundaryResult(
                new AiBoundaryDecision(
                        agent.pipelineStatus(),
                        clinicalDataAvailable(agent),
                        agent.decision(),
                        true,
                        false,
                        false),
                input.contract().contractVersion(),
                input.contract().destination(),
                agent.reasonCode(),
                agent.warnings(),
                medicationRequestsStatus(diagnosis),
                agent.contractValid(),
                agent.usable(),
                correlationId);
    }

    private static boolean clinicalDataAvailable(DeterministicAgentResult agent) {
        if (agent.decision() == AgentDecision.BLOCKED) {
            return false;
        }
        return !AgentReasonCodes.INSUFFICIENT_CLINICAL_DATA.equals(agent.reasonCode());
    }

    private static String medicationRequestsStatus(PipelineDiagnosis diagnosis) {
        if (diagnosis == null || diagnosis.stages() == null) {
            return PipelineStageStatus.NOT_REQUESTED.name();
        }
        return diagnosis.stages().stream()
                .filter(stage -> stage != null && "medicationRequests".equals(stage.stage()))
                .map(PipelineStageDiagnosis::status)
                .findFirst()
                .map(PipelineStageStatus::name)
                .orElse(PipelineStageStatus.NOT_REQUESTED.name());
    }
}

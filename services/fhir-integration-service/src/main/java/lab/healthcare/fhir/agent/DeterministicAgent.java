package lab.healthcare.fhir.agent;

import lab.healthcare.fhir.agentstub.AgentStub;
import lab.healthcare.fhir.agentstub.AgentStubObservation;
import lab.healthcare.fhir.pipeline.PipelineDiagnoses;
import lab.healthcare.fhir.pipeline.PipelineDiagnosis;
import lab.healthcare.fhir.pipeline.PipelineStageDiagnosis;
import lab.healthcare.fhir.pipeline.PipelineStageStatus;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotOutcome;

import java.util.ArrayList;
import java.util.List;

/**
 * Applies explicit rules to an authorized v1 contract. Does not fetch FHIR,
 * call a model, or emit clinical advice.
 */
public final class DeterministicAgent {

    private DeterministicAgent() {
    }

    public static DeterministicAgentResult evaluate(DeterministicAgentInput input) {
        if (input == null) {
            throw new AgentValidationException("Deterministic agent input must be provided");
        }
        PipelineDiagnosis diagnosis = input.diagnosis() == null
                ? PipelineDiagnoses.fromContract(input.contract())
                : input.diagnosis();
        List<String> warnings = warningsFrom(diagnosis);
        AgentStubObservation observation;
        try {
            observation = AgentStub.observe(input.contract());
        } catch (RuntimeException ex) {
            return result(
                    AgentDecision.BLOCKED,
                    AgentReasonCodes.CONTRACT_REJECTED,
                    List.of(AgentReasonCodes.CONTRACT_REJECTED),
                    warnings,
                    diagnosis);
        }
        if (unusableOutcome(input.contract().outcome())
                || !diagnosis.usable()
                || !diagnosis.contractValid()
                || blocking(diagnosis.overall())) {
            return result(
                    AgentDecision.BLOCKED,
                    AgentReasonCodes.PIPELINE_NOT_USABLE,
                    List.of(AgentReasonCodes.PIPELINE_NOT_USABLE),
                    warnings,
                    diagnosis);
        }
        if (!observation.hasClinicalData()) {
            return result(
                    AgentDecision.REQUIRES_HUMAN_REVIEW,
                    AgentReasonCodes.INSUFFICIENT_CLINICAL_DATA,
                    List.of(AgentReasonCodes.INSUFFICIENT_CLINICAL_DATA),
                    warnings,
                    diagnosis);
        }
        if (diagnosis.overall() == PipelineStageStatus.PARTIAL) {
            return result(
                    AgentDecision.REQUIRES_HUMAN_REVIEW,
                    AgentReasonCodes.PIPELINE_PARTIAL,
                    List.of(AgentReasonCodes.PIPELINE_PARTIAL),
                    warnings,
                    diagnosis);
        }
        return result(
                AgentDecision.READY,
                AgentReasonCodes.READY_FOR_BOUNDARY,
                List.of(),
                warnings,
                diagnosis);
    }

    private static boolean unusableOutcome(ClinicalSnapshotOutcome outcome) {
        return outcome == ClinicalSnapshotOutcome.AUTHENTICATION_REQUIRED
                || outcome == ClinicalSnapshotOutcome.PATIENT_CONTEXT_NOT_CONFIGURED
                || outcome == ClinicalSnapshotOutcome.SNAPSHOT_UNAVAILABLE;
    }

    private static boolean blocking(PipelineStageStatus status) {
        return status == PipelineStageStatus.FAILED
                || status == PipelineStageStatus.REJECTED
                || status == PipelineStageStatus.AUTHENTICATION_FAILED
                || status == PipelineStageStatus.VALIDATION_FAILED
                || status == PipelineStageStatus.PROVIDER_ERROR
                || status == PipelineStageStatus.TIMEOUT;
    }

    private static List<String> warningsFrom(PipelineDiagnosis diagnosis) {
        List<String> warnings = new ArrayList<>();
        if (diagnosis == null || diagnosis.stages() == null) {
            return List.of();
        }
        for (PipelineStageDiagnosis stage : diagnosis.stages()) {
            if (stage == null) {
                continue;
            }
            if (Boolean.TRUE.equals(stage.truncated())) {
                warnings.add("truncated:" + stage.stage());
            }
            if (stage.status() == PipelineStageStatus.NOT_REQUESTED) {
                warnings.add("not-requested:" + stage.stage());
            }
            if (stage.status() == PipelineStageStatus.NOT_AVAILABLE) {
                warnings.add("not-available:" + stage.stage());
            }
            if (stage.status() == PipelineStageStatus.TIMEOUT && !stage.critical()) {
                warnings.add("timeout:" + stage.stage());
            }
        }
        return List.copyOf(warnings);
    }

    private static DeterministicAgentResult result(
            AgentDecision decision,
            String reasonCode,
            List<String> findings,
            List<String> warnings,
            PipelineDiagnosis diagnosis) {
        PipelineStageStatus pipelineStatus =
                diagnosis == null || diagnosis.overall() == null ? PipelineStageStatus.FAILED : diagnosis.overall();
        boolean contractValid = diagnosis != null && diagnosis.contractValid();
        boolean usable = diagnosis != null && diagnosis.usable();
        return new DeterministicAgentResult(
                decision,
                reasonCode,
                findings,
                warnings,
                true,
                false,
                pipelineStatus,
                contractValid,
                usable);
    }
}

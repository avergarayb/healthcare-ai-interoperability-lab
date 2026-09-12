package lab.healthcare.fhir.pipeline;

import java.util.List;

/**
 * Aggregate technical diagnosis. Separates overall status from contract
 * usability. Never includes clinical values.
 */
public record PipelineDiagnosis(
        PipelineStageStatus overall,
        boolean contractValid,
        boolean usable,
        List<PipelineStageDiagnosis> stages) {

    public PipelineDiagnosis {
        if (overall == null) {
            throw new IllegalArgumentException("Pipeline overall status must be provided");
        }
        stages = stages == null ? List.of() : List.copyOf(stages);
    }

    @Override
    public String toString() {
        return "PipelineDiagnosis[overall="
                + overall
                + ", contractValid="
                + contractValid
                + ", usable="
                + usable
                + ", stages="
                + stages.size()
                + "]";
    }
}

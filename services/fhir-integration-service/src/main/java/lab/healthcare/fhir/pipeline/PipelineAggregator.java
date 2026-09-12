package lab.healthcare.fhir.pipeline;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

/**
 * Deterministic aggregation. Critical failures win over non-critical
 * {@code PARTIAL}. {@code NOT_REQUESTED} never fails the run.
 */
public final class PipelineAggregator {

    private static final List<PipelineStageStatus> CRITICAL_PRIORITY = List.of(
            PipelineStageStatus.REJECTED,
            PipelineStageStatus.AUTHENTICATION_FAILED,
            PipelineStageStatus.VALIDATION_FAILED,
            PipelineStageStatus.FAILED,
            PipelineStageStatus.PROVIDER_ERROR,
            PipelineStageStatus.TIMEOUT);

    private PipelineAggregator() {
    }

    public static PipelineStageStatus overall(List<PipelineStageDiagnosis> stages) {
        List<PipelineStageDiagnosis> safe = stages == null ? List.of() : stages;
        List<PipelineStageStatus> criticalFailures = new ArrayList<>();
        boolean nonCriticalIssue = false;
        for (PipelineStageDiagnosis stage : safe) {
            if (stage == null || stage.status() == PipelineStageStatus.NOT_REQUESTED) {
                continue;
            }
            if (stage.critical() && isFailure(stage.status())) {
                criticalFailures.add(stage.status());
            } else if (!stage.critical() && stage.status() != PipelineStageStatus.SUCCESS) {
                nonCriticalIssue = true;
            }
        }
        if (!criticalFailures.isEmpty()) {
            criticalFailures.sort(Comparator.comparingInt(CRITICAL_PRIORITY::indexOf));
            return criticalFailures.get(0);
        }
        if (nonCriticalIssue) {
            return PipelineStageStatus.PARTIAL;
        }
        return PipelineStageStatus.SUCCESS;
    }

    public static boolean usable(PipelineStageStatus overall) {
        return overall == PipelineStageStatus.SUCCESS || overall == PipelineStageStatus.PARTIAL;
    }

    private static boolean isFailure(PipelineStageStatus status) {
        return status != PipelineStageStatus.SUCCESS && status != PipelineStageStatus.PARTIAL;
    }
}

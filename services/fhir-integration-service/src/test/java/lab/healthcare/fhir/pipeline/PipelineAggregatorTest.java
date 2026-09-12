package lab.healthcare.fhir.pipeline;

import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class PipelineAggregatorTest {

    @Test
    void allSuccessIsSuccess() {
        assertThat(PipelineAggregator.overall(List.of(
                        PipelineStageDiagnosis.of("patient", PipelineStageStatus.SUCCESS, true),
                        PipelineStageDiagnosis.collection(
                                "conditions", PipelineStageStatus.SUCCESS, 1, 1, false, null))))
                .isEqualTo(PipelineStageStatus.SUCCESS);
        assertThat(PipelineAggregator.usable(PipelineStageStatus.SUCCESS)).isTrue();
    }

    @Test
    void nonCriticalTimeoutIsPartial() {
        assertThat(PipelineAggregator.overall(List.of(
                        PipelineStageDiagnosis.of("patient", PipelineStageStatus.SUCCESS, true),
                        PipelineStageDiagnosis.collection(
                                "observations",
                                PipelineStageStatus.TIMEOUT,
                                null,
                                null,
                                null,
                                new PipelineErrorInfo(
                                        PipelineErrorCodes.FHIR_TIMEOUT, "TIMEOUT", true, "timed out", null)))))
                .isEqualTo(PipelineStageStatus.PARTIAL);
        assertThat(PipelineAggregator.usable(PipelineStageStatus.PARTIAL)).isTrue();
    }

    @Test
    void criticalFailureWinsOverNonCriticalPartial() {
        assertThat(PipelineAggregator.overall(List.of(
                        PipelineStageDiagnosis.of("patient", PipelineStageStatus.FAILED, true),
                        PipelineStageDiagnosis.collection(
                                "conditions", PipelineStageStatus.TIMEOUT, null, null, null, null))))
                .isEqualTo(PipelineStageStatus.FAILED);
        assertThat(PipelineAggregator.usable(PipelineStageStatus.FAILED)).isFalse();
    }

    @Test
    void notRequestedDoesNotFailTheRun() {
        assertThat(PipelineAggregator.overall(List.of(
                        PipelineStageDiagnosis.of("patient", PipelineStageStatus.SUCCESS, true),
                        PipelineStageDiagnosis.of("medicationRequests", PipelineStageStatus.NOT_REQUESTED, false))))
                .isEqualTo(PipelineStageStatus.SUCCESS);
    }

    @Test
    void notAvailableIsPartialWhenNonCritical() {
        assertThat(PipelineAggregator.overall(List.of(
                        PipelineStageDiagnosis.of("patient", PipelineStageStatus.SUCCESS, true),
                        PipelineStageDiagnosis.of("diagnosticReports", PipelineStageStatus.NOT_AVAILABLE, false))))
                .isEqualTo(PipelineStageStatus.PARTIAL);
    }

    @Test
    void rejectedHasPriorityOverAuthentication() {
        assertThat(PipelineAggregator.overall(List.of(
                        PipelineStageDiagnosis.of("patient", PipelineStageStatus.AUTHENTICATION_FAILED, true),
                        PipelineStageDiagnosis.of("agentStub", PipelineStageStatus.REJECTED, true))))
                .isEqualTo(PipelineStageStatus.REJECTED);
    }
}

package lab.healthcare.fhir.pipeline;

import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class SafePipelineLogTest {

    @Test
    void lineIsStructuredAndOmitsClinicalValues() {
        PipelineDiagnosis diagnosis = new PipelineDiagnosis(
                PipelineStageStatus.PARTIAL,
                true,
                true,
                List.of(PipelineStageDiagnosis.collection(
                        "observations", PipelineStageStatus.TIMEOUT, 0, 0, false, null)));

        String line = SafePipelineLog.line(diagnosis, "epic-sandbox");

        assertThat(line).startsWith("PIPELINE");
        assertThat(line).contains("destination=epic-sandbox");
        assertThat(line).contains("overall=PARTIAL");
        assertThat(line).contains("observations=TIMEOUT");
        assertThat(line).doesNotContain("Patient/");
        assertThat(line).doesNotContain("access_token");
    }

    @Test
    void credentialsAreRejected() {
        assertThatThrownBy(() -> SafePipelineLog.sanitize("Bearer secret"))
                .isInstanceOf(IllegalStateException.class);
    }
}

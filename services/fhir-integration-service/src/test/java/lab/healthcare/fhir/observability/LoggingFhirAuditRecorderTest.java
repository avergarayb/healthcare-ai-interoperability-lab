package lab.healthcare.fhir.observability;

import lab.healthcare.fhir.exception.FhirErrorCategory;

import org.junit.jupiter.api.Test;

import java.time.Instant;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class LoggingFhirAuditRecorderTest {

    @Test
    void recordsSuccessfulAndFailedEventsInOrder() {
        LoggingFhirAuditRecorder recorder = new LoggingFhirAuditRecorder();
        FhirOperationContext context = new FhirOperationContext(
                "corr-1", "local-hapi", FhirAuditOperation.READ, "Patient", "patient-001");
        FhirAuditEvent success = new FhirAuditEvent(
                Instant.parse("2026-08-27T12:00:00Z"), context, FhirAuditOutcome.SUCCESS, 200, 10, null);
        FhirAuditEvent failure = new FhirAuditEvent(
                Instant.parse("2026-08-27T12:00:01Z"),
                new FhirOperationContext("corr-1", "does-not-exist", FhirAuditOperation.READ, "Patient", "patient-001"),
                FhirAuditOutcome.FAILURE,
                null,
                3,
                FhirErrorCategory.VALIDATION_ERROR);

        recorder.record(success);
        recorder.record(failure);

        assertThat(recorder.recorded()).containsExactly(success, failure);
        assertThat(recorder.recorded().getFirst().toLogLine()).contains("outcome=SUCCESS");
        assertThat(recorder.recorded().getLast().toLogLine()).contains("error=VALIDATION_ERROR");
    }

    @Test
    void rejectsNullEvent() {
        assertThatThrownBy(() -> new LoggingFhirAuditRecorder().record(null))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("Audit event");
    }
}

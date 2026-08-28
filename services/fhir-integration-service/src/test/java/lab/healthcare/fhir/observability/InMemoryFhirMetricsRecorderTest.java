package lab.healthcare.fhir.observability;

import lab.healthcare.fhir.exception.FhirErrorCategory;

import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.Map;
import java.util.Set;
import java.util.stream.Stream;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class InMemoryFhirMetricsRecorderTest {

    private final InMemoryFhirMetricsRecorder recorder = new InMemoryFhirMetricsRecorder();

    @Test
    void successfulOperationIncrementsSuccessAndTotalCounters() {
        recorder.record(success("corr-ok", "local-hapi", "Patient", "patient-001", 41));

        FhirMetricSnapshot snapshot = recorder.snapshot();
        assertThat(snapshot.totalOperations()).isEqualTo(1);
        assertThat(snapshot.successfulOperations()).isEqualTo(1);
        assertThat(snapshot.failedOperations()).isZero();
        assertThat(snapshot.operationsByOutcome()).containsEntry("SUCCESS", 1L);
    }

    @Test
    void failedOperationIncrementsFailureAndTotalCounters() {
        recorder.record(failure("corr-fail", "does-not-exist", "Patient", "patient-001", 5));

        FhirMetricSnapshot snapshot = recorder.snapshot();
        assertThat(snapshot.totalOperations()).isEqualTo(1);
        assertThat(snapshot.successfulOperations()).isZero();
        assertThat(snapshot.failedOperations()).isEqualTo(1);
        assertThat(snapshot.operationsByOutcome()).containsEntry("FAILURE", 1L);
    }

    @Test
    void aggregatesOperationsDestinationsAndResourceTypes() {
        recorder.record(success("corr-1", "local-hapi", "Patient", "patient-001", 10));
        recorder.record(success("corr-2", "local-hapi", "Patient", "patient-002", 20));
        recorder.record(success("corr-3", "secured-lab", "Observation", "obs-001", 30));
        recorder.record(failure("corr-4", "does-not-exist", "Patient", "patient-001", 4));

        FhirMetricSnapshot snapshot = recorder.snapshot();
        assertThat(snapshot.totalOperations()).isEqualTo(4);
        assertThat(snapshot.successfulOperations()).isEqualTo(3);
        assertThat(snapshot.failedOperations()).isEqualTo(1);
        assertThat(snapshot.operationsByType()).containsExactly(Map.entry("READ", 4L));
        assertThat(snapshot.operationsByDestination())
                .containsEntry("local-hapi", 2L)
                .containsEntry("secured-lab", 1L)
                .containsEntry("does-not-exist", 1L);
        assertThat(snapshot.operationsByResourceType())
                .containsEntry("Patient", 3L)
                .containsEntry("Observation", 1L);
    }

    @Test
    void aggregatesDurationAndComputesIntegerAverage() {
        recorder.record(success("corr-a", "local-hapi", "Patient", "patient-001", 10));
        recorder.record(success("corr-b", "local-hapi", "Patient", "patient-002", 11));

        FhirMetricSnapshot snapshot = recorder.snapshot();
        assertThat(snapshot.totalDurationMs()).isEqualTo(21);
        assertThat(snapshot.operationCount()).isEqualTo(2);
        assertThat(snapshot.averageDurationMs()).isEqualTo(10);
    }

    @Test
    void emptySnapshotHasZeroAverageDuration() {
        FhirMetricSnapshot snapshot = recorder.snapshot();
        assertThat(snapshot.totalOperations()).isZero();
        assertThat(snapshot.averageDurationMs()).isZero();
        assertThat(snapshot.toSummaryLine()).startsWith("FHIR_METRICS");
    }

    @Test
    void doesNotUseHighCardinalityOrSensitiveFieldsAsDimensions() {
        recorder.record(failure(
                "abc-123-correlation",
                "local-hapi",
                "Patient",
                "patient-001",
                7));

        FhirMetricSnapshot snapshot = recorder.snapshot();
        assertThat(snapshot.operationsByDestination().keySet()).containsExactly("local-hapi");
        assertThat(snapshot.operationsByType().keySet()).containsExactly("READ");
        assertThat(snapshot.operationsByResourceType().keySet()).containsExactly("Patient");
        assertThat(snapshot.operationsByOutcome().keySet()).containsExactly("FAILURE");
        assertThat(allDimensionKeys(snapshot)).doesNotContain("abc-123-correlation");
        assertThat(allDimensionKeys(snapshot)).doesNotContain("patient-001");
        assertThat(allDimensionKeys(snapshot)).doesNotContain("VALIDATION_ERROR");

        String summary = snapshot.toSummaryLine();
        assertThat(summary).doesNotContain("abc-123-correlation");
        assertThat(summary).doesNotContain("patient-001");
        assertThat(summary).doesNotContain("access_token");
        assertThat(summary).doesNotContain("client_secret");
        assertThat(summary).doesNotContain("refresh_token");
        assertThat(summary).doesNotContain("authorization_code");
        assertThat(summary).doesNotContain("code_verifier");
        assertThat(summary).doesNotContain("Bearer ");
        assertThat(summary).doesNotContain("Garcia");
        assertThat(summary).doesNotContain("resourceType\":\"Patient");
        assertThat(summary).doesNotContain("VALIDATION_ERROR");
    }

    @Test
    void rejectsNullEvent() {
        assertThatThrownBy(() -> recorder.record(null))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("Audit event");
    }

    private static String[] allDimensionKeys(FhirMetricSnapshot snapshot) {
        return Stream.of(
                        snapshot.operationsByType().keySet(),
                        snapshot.operationsByDestination().keySet(),
                        snapshot.operationsByResourceType().keySet(),
                        snapshot.operationsByOutcome().keySet())
                .flatMap(Set::stream)
                .toArray(String[]::new);
    }

    private static FhirAuditEvent success(
            String correlationId, String destination, String resourceType, String resourceId, long durationMs) {
        return new FhirAuditEvent(
                Instant.parse("2026-08-27T12:00:00Z"),
                new FhirOperationContext(correlationId, destination, FhirAuditOperation.READ, resourceType, resourceId),
                FhirAuditOutcome.SUCCESS,
                200,
                durationMs,
                null);
    }

    private static FhirAuditEvent failure(
            String correlationId, String destination, String resourceType, String resourceId, long durationMs) {
        return new FhirAuditEvent(
                Instant.parse("2026-08-27T12:00:00Z"),
                new FhirOperationContext(correlationId, destination, FhirAuditOperation.READ, resourceType, resourceId),
                FhirAuditOutcome.FAILURE,
                null,
                durationMs,
                FhirErrorCategory.VALIDATION_ERROR);
    }
}

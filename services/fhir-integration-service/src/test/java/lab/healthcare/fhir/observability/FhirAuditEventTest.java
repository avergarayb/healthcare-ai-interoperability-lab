package lab.healthcare.fhir.observability;

import lab.healthcare.fhir.exception.FhirErrorCategory;

import org.junit.jupiter.api.Test;

import java.time.Instant;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class FhirAuditEventTest {

    @Test
    void successLogLineContainsTraceFieldsAndOmitsCredentials() {
        FhirAuditEvent event = new FhirAuditEvent(
                Instant.parse("2026-08-27T12:00:00Z"),
                new FhirOperationContext("abc-123", "local-hapi", FhirAuditOperation.READ, "Patient", "patient-001"),
                FhirAuditOutcome.SUCCESS,
                200,
                41,
                null);

        String line = event.toLogLine();

        assertThat(line).startsWith("FHIR_AUDIT ");
        assertThat(line).contains("correlationId=abc-123");
        assertThat(line).contains("destination=local-hapi");
        assertThat(line).contains("operation=READ");
        assertThat(line).contains("resourceType=Patient");
        assertThat(line).contains("resourceId=patient-001");
        assertThat(line).contains("outcome=SUCCESS");
        assertThat(line).contains("status=200");
        assertThat(line).contains("durationMs=41");
        assertThat(line).doesNotContain("access_token");
        assertThat(line).doesNotContain("client_secret");
        assertThat(line).doesNotContain("refresh_token");
        assertThat(line).doesNotContain("authorization_code");
        assertThat(line).doesNotContain("Bearer ");
        assertThat(line).doesNotContain("resourceType\":\"Patient");
        assertThat(line).doesNotContain("Garcia");
    }

    @Test
    void failureLogLineUsesErrorCategoryNotPayload() {
        FhirAuditEvent event = new FhirAuditEvent(
                Instant.parse("2026-08-27T12:00:00Z"),
                new FhirOperationContext("def-456", "does-not-exist", FhirAuditOperation.READ, "Patient", "patient-001"),
                FhirAuditOutcome.FAILURE,
                null,
                5,
                FhirErrorCategory.VALIDATION_ERROR);

        String line = event.toLogLine();

        assertThat(line).contains("outcome=FAILURE");
        assertThat(line).contains("error=VALIDATION_ERROR");
        assertThat(line).contains("destination=does-not-exist");
        assertThat(line).doesNotContain("access_token");
        assertThat(line).doesNotContain("{");
    }

    @Test
    void failureRequiresErrorCategory() {
        assertThatThrownBy(() -> new FhirAuditEvent(
                        Instant.parse("2026-08-27T12:00:00Z"),
                        new FhirOperationContext("abc", "local-hapi", FhirAuditOperation.READ, "Patient", "patient-001"),
                        FhirAuditOutcome.FAILURE,
                        404,
                        1,
                        null))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("error category");
    }
}

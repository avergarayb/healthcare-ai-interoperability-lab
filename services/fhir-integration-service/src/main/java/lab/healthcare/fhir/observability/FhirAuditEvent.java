package lab.healthcare.fhir.observability;

import lab.healthcare.fhir.exception.FhirErrorCategory;

import java.time.Instant;
import java.util.Locale;
import java.util.StringJoiner;

public record FhirAuditEvent(
        Instant timestamp,
        FhirOperationContext context,
        FhirAuditOutcome outcome,
        Integer status,
        long durationMs,
        FhirErrorCategory error) {

    public FhirAuditEvent {
        if (timestamp == null) {
            throw new IllegalArgumentException("Audit timestamp must be provided");
        }
        if (context == null) {
            throw new IllegalArgumentException("Audit context must be provided");
        }
        if (outcome == null) {
            throw new IllegalArgumentException("Audit outcome must be provided");
        }
        if (durationMs < 0) {
            throw new IllegalArgumentException("Audit duration must be zero or positive");
        }
        if (outcome == FhirAuditOutcome.FAILURE && error == null) {
            throw new IllegalArgumentException("Failed audit event must include an error category");
        }
        if (outcome == FhirAuditOutcome.SUCCESS) {
            error = null;
        }
    }

    public String toLogLine() {
        StringJoiner line = new StringJoiner(" ");
        line.add("FHIR_AUDIT");
        add(line, "correlationId", context.correlationId());
        add(line, "destination", context.destination());
        add(line, "operation", context.operation().name());
        add(line, "resourceType", context.resourceType());
        add(line, "resourceId", context.resourceId());
        add(line, "outcome", outcome.name());
        if (status != null) {
            add(line, "status", Integer.toString(status));
        }
        add(line, "durationMs", Long.toString(durationMs));
        if (error != null) {
            add(line, "error", error.name());
        }
        return requireSafe(line.toString());
    }

    private static void add(StringJoiner line, String key, String value) {
        if (value == null || value.isBlank()) {
            return;
        }
        line.add(key + "=" + value);
    }

    static String requireSafe(String line) {
        String lower = line.toLowerCase(Locale.ROOT);
        if (lower.contains("access_token=")
                || lower.contains("client_secret=")
                || lower.contains("refresh_token=")
                || lower.contains("authorization_code=")
                || lower.contains("code_verifier=")
                || lower.contains("bearer ")) {
            throw new IllegalStateException("Audit log line must not contain credentials");
        }
        return line;
    }
}

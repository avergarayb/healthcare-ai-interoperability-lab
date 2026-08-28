package lab.healthcare.fhir.exception;

import java.util.Locale;
import java.util.StringJoiner;

/**
 * Safe diagnostic fields for an integration failure. No tokens, secrets, or
 * complete FHIR payloads.
 */
public record FhirErrorDetails(
        FhirErrorCategory category,
        Integer status,
        String operation,
        String destination,
        String resourceType,
        String resourceId,
        String message) {

    public FhirErrorDetails {
        if (category == null) {
            throw new IllegalArgumentException("Error category must be provided");
        }
        operation = blankToNull(operation);
        destination = blankToNull(destination);
        resourceType = blankToNull(resourceType);
        resourceId = blankToNull(resourceId);
        message = requireSafe(message == null || message.isBlank() ? category.safeMessage() : message.trim());
    }

    public static FhirErrorDetails of(FhirErrorCategory category, Integer status) {
        return new FhirErrorDetails(category, status, null, null, null, null, category.safeMessage());
    }

    public static FhirErrorDetails of(FhirErrorCategory category, Integer status, String message) {
        return new FhirErrorDetails(category, status, null, null, null, null, message);
    }

    public String toLogLine() {
        StringJoiner line = new StringJoiner(" ");
        line.add("FHIR_ERROR");
        line.add("category=" + category.name());
        if (status != null) {
            line.add("status=" + status);
        }
        add(line, "operation", operation);
        add(line, "destination", destination);
        add(line, "resourceType", resourceType);
        add(line, "resourceId", resourceId);
        add(line, "message", message);
        return requireSafe(line.toString());
    }

    private static void add(StringJoiner line, String key, String value) {
        if (value == null) {
            return;
        }
        line.add(key + "=" + value);
    }

    private static String blankToNull(String value) {
        return value == null || value.isBlank() ? null : value.trim();
    }

    static String requireSafe(String text) {
        String lower = text.toLowerCase(Locale.ROOT);
        if (lower.contains("access_token=")
                || lower.contains("client_secret=")
                || lower.contains("refresh_token=")
                || lower.contains("authorization_code=")
                || lower.contains("code_verifier=")
                || lower.contains("bearer ")) {
            throw new IllegalStateException("Error details must not contain credentials");
        }
        return text;
    }
}

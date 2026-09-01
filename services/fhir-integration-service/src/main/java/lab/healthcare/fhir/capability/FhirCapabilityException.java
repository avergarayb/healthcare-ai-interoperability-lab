package lab.healthcare.fhir.capability;

import java.util.Locale;

/**
 * The document is not a usable CapabilityStatement. Distinct from transport
 * failures classified by {@code FhirClientException}.
 */
public class FhirCapabilityException extends RuntimeException {

    public FhirCapabilityException(String message) {
        super(requireSafe(message));
    }

    public FhirCapabilityException(String message, Throwable cause) {
        super(requireSafe(message), cause);
    }

    static String requireSafe(String message) {
        String text = message == null || message.isBlank()
                ? "FHIR capability discovery failed"
                : message.trim();
        String lower = text.toLowerCase(Locale.ROOT);
        if (lower.contains("access_token=")
                || lower.contains("refresh_token=")
                || lower.contains("client_secret=")
                || lower.contains("begin private key")
                || lower.contains("code_verifier=")
                || lower.contains("bearer ")) {
            throw new IllegalStateException("Capability discovery message must not contain credentials");
        }
        return text;
    }
}

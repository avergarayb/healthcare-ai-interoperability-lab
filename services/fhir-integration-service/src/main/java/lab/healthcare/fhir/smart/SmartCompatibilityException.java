package lab.healthcare.fhir.smart;

import java.util.Locale;

/**
 * Discovered SMART metadata cannot support the required authorization flow.
 * Distinct from {@link lab.healthcare.fhir.auth.oauth2.OAuth2TokenException}, which is a token HTTP failure.
 */
public class SmartCompatibilityException extends RuntimeException {

    public SmartCompatibilityException(String message) {
        super(requireSafe(message));
    }

    static String requireSafe(String message) {
        String text = message == null || message.isBlank()
                ? "SMART metadata is incompatible with the required authorization flow"
                : message.trim();
        String lower = text.toLowerCase(Locale.ROOT);
        if (lower.contains("access_token")
                || lower.contains("refresh_token")
                || lower.contains("client_secret")
                || lower.contains("code_verifier")
                || lower.contains("authorization_code=")
                || lower.contains("bearer ")) {
            throw new IllegalStateException("SMART compatibility message must not contain credentials");
        }
        return text;
    }
}

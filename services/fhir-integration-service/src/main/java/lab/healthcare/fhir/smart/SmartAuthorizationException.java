package lab.healthcare.fhir.smart;

import java.util.Locale;

/**
 * Interactive SMART authorization failed locally (state, callback, session).
 * Distinct from token-endpoint HTTP ({@code OAuth2TokenException}) and FHIR errors.
 */
public class SmartAuthorizationException extends RuntimeException {

    public SmartAuthorizationException(String message) {
        super(requireSafe(message));
    }

    static String requireSafe(String message) {
        String text = message == null || message.isBlank()
                ? "SMART authorization failed"
                : message.trim();
        String lower = text.toLowerCase(Locale.ROOT);
        if (lower.contains("access_token=")
                || lower.contains("refresh_token=")
                || lower.contains("client_secret=")
                || lower.contains("code_verifier=")
                || lower.contains("authorization_code=")
                || lower.contains("begin private key")
                || lower.contains("bearer ")) {
            throw new IllegalStateException("SMART authorization message must not contain credentials");
        }
        return text;
    }
}

package lab.healthcare.fhir.vendor.oracle;

import java.util.Locale;

/**
 * Oracle Health profile is incomplete or incompatible with the intended integration mode.
 */
public class OracleHealthProfileException extends RuntimeException {

    public OracleHealthProfileException(String message) {
        super(requireSafe(message));
    }

    static String requireSafe(String message) {
        String text = message == null || message.isBlank()
                ? "Oracle Health integration profile is invalid"
                : message.trim();
        String lower = text.toLowerCase(Locale.ROOT);
        if (lower.contains("access_token=")
                || lower.contains("refresh_token=")
                || lower.contains("client_secret=")
                || lower.contains("begin private key")
                || lower.contains("code_verifier=")
                || lower.contains("bearer ")) {
            throw new IllegalStateException("Oracle Health profile message must not contain credentials");
        }
        return text;
    }
}

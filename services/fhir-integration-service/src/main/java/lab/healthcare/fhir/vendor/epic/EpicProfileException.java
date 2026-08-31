package lab.healthcare.fhir.vendor.epic;

import java.util.Locale;

/**
 * Epic profile is incomplete or incompatible with the intended integration mode.
 */
public class EpicProfileException extends RuntimeException {

    public EpicProfileException(String message) {
        super(requireSafe(message));
    }

    static String requireSafe(String message) {
        String text = message == null || message.isBlank()
                ? "Epic integration profile is invalid"
                : message.trim();
        String lower = text.toLowerCase(Locale.ROOT);
        if (lower.contains("access_token=")
                || lower.contains("refresh_token=")
                || lower.contains("client_secret=")
                || lower.contains("begin private key")
                || lower.contains("code_verifier=")
                || lower.contains("bearer ")) {
            throw new IllegalStateException("Epic profile message must not contain credentials");
        }
        return text;
    }
}

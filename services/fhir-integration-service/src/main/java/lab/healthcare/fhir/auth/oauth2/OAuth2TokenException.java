package lab.healthcare.fhir.auth.oauth2;

import java.util.Locale;

public class OAuth2TokenException extends RuntimeException {

    private final int httpStatus;
    private final String error;
    private final String errorDescription;

    public OAuth2TokenException(String message) {
        this(message, null, 0, null, null);
    }

    public OAuth2TokenException(String message, Throwable cause) {
        this(message, cause, 0, null, null);
    }

    public OAuth2TokenException(String message, int httpStatus, String error, String errorDescription) {
        this(message, null, httpStatus, error, errorDescription);
    }

    private OAuth2TokenException(
            String message, Throwable cause, int httpStatus, String error, String errorDescription) {
        super(message, cause);
        this.httpStatus = httpStatus;
        this.error = blankToNull(error);
        this.errorDescription = sanitizeDescription(errorDescription);
    }

    public int httpStatus() {
        return httpStatus;
    }

    public String error() {
        return error;
    }

    public String errorDescription() {
        return errorDescription;
    }

    private static String blankToNull(String value) {
        return value == null || value.isBlank() ? null : value.trim();
    }

    private static String sanitizeDescription(String value) {
        String text = blankToNull(value);
        if (text == null) {
            return null;
        }
        String lower = text.toLowerCase(Locale.ROOT);
        if (lower.contains("access_token=")
                || lower.contains("refresh_token=")
                || lower.contains("client_secret=")
                || lower.contains("code_verifier=")
                || lower.contains("authorization_code=")
                || lower.contains("begin private key")
                || lower.contains("bearer ")) {
            return null;
        }
        return text;
    }
}

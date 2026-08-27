package lab.healthcare.fhir.auth.oauth2;

public class OAuth2TokenException extends RuntimeException {

    public OAuth2TokenException(String message) {
        super(message);
    }

    public OAuth2TokenException(String message, Throwable cause) {
        super(message, cause);
    }
}

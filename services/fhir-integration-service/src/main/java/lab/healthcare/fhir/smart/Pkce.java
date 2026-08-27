package lab.healthcare.fhir.smart;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.util.Base64;

public final class Pkce {

    private static final SecureRandom RANDOM = new SecureRandom();

    private Pkce() {
    }

    public static String codeVerifier() {
        byte[] bytes = new byte[32];
        RANDOM.nextBytes(bytes);
        return base64Url(bytes);
    }

    public static String codeChallengeS256(String codeVerifier) {
        if (codeVerifier == null || codeVerifier.isBlank()) {
            throw new IllegalArgumentException("PKCE code_verifier must be provided");
        }
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hashed = digest.digest(codeVerifier.getBytes(StandardCharsets.US_ASCII));
            return base64Url(hashed);
        } catch (Exception ex) {
            throw new IllegalStateException("Unable to compute PKCE S256 challenge", ex);
        }
    }

    public static String newState() {
        byte[] bytes = new byte[24];
        RANDOM.nextBytes(bytes);
        return base64Url(bytes);
    }

    private static String base64Url(byte[] bytes) {
        return Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
    }
}

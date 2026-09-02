package lab.healthcare.fhir.auth.oauth2;

import lab.healthcare.fhir.auth.AccessToken;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;

public final class OAuth2TokenResponseParser {

    private final ObjectMapper objectMapper;
    private final Clock clock;

    public OAuth2TokenResponseParser(ObjectMapper objectMapper, Clock clock) {
        this.objectMapper = objectMapper;
        this.clock = clock;
    }

    public AccessToken parse(int statusCode, String body) {
        JsonNode json = readJson(body);
        if (statusCode < 200 || statusCode >= 300) {
            String error = text(json, "error");
            String errorDescription = text(json, "error_description");
            throw new OAuth2TokenException(
                    "OAuth token acquisition failed: HTTP " + statusCode
                            + (error == null ? "" : " " + error),
                    statusCode,
                    error,
                    errorDescription);
        }
        String token = text(json, "access_token");
        if (token == null || token.isBlank()) {
            throw new OAuth2TokenException("OAuth token acquisition failed: response has no access_token");
        }
        long expiresIn = json.hasNonNull("expires_in") ? json.get("expires_in").asLong(0L) : 0L;
        Instant expiresAt = Instant.now(clock).plus(Duration.ofSeconds(Math.max(expiresIn, 0L)));
        return new AccessToken(
                token,
                expiresAt,
                text(json, "refresh_token"),
                text(json, "scope"),
                text(json, "patient"));
    }

    private JsonNode readJson(String body) {
        if (body == null || body.isBlank()) {
            throw new OAuth2TokenException("OAuth token acquisition failed: empty response");
        }
        try {
            return objectMapper.readTree(body);
        } catch (Exception ex) {
            throw new OAuth2TokenException("OAuth token acquisition failed: response is not JSON", ex);
        }
    }

    private static String text(JsonNode json, String field) {
        if (json == null || !json.hasNonNull(field)) {
            return null;
        }
        return json.get(field).asText();
    }
}

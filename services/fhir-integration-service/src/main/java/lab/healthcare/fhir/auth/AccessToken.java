package lab.healthcare.fhir.auth;

import java.time.Duration;
import java.time.Instant;

public record AccessToken(String value, Instant expiresAt, String refreshToken, String scope, String patient) {

    public AccessToken(String value, Instant expiresAt) {
        this(value, expiresAt, null, null, null);
    }

    public boolean isUsableAt(Instant now, Duration skew) {
        if (value == null || value.isBlank() || expiresAt == null || now == null) {
            return false;
        }
        Duration safety = skew == null ? Duration.ZERO : skew;
        return now.plus(safety).isBefore(expiresAt);
    }
}

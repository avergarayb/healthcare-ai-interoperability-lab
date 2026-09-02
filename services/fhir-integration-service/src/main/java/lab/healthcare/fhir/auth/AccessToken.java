package lab.healthcare.fhir.auth;

import java.time.Duration;
import java.time.Instant;

public record AccessToken(String value, Instant expiresAt, String refreshToken, String scope, String patient) {

    public AccessToken(String value, Instant expiresAt) {
        this(value, expiresAt, null, null, null);
    }

    @Override
    public String toString() {
        return "AccessToken[hasValue="
                + (value != null && !value.isBlank())
                + ", expiresAt="
                + expiresAt
                + ", hasRefreshToken="
                + (refreshToken != null && !refreshToken.isBlank())
                + ", hasScope="
                + (scope != null && !scope.isBlank())
                + ", hasPatient="
                + (patient != null && !patient.isBlank())
                + "]";
    }

    public boolean isUsableAt(Instant now, Duration skew) {
        if (value == null || value.isBlank() || expiresAt == null || now == null) {
            return false;
        }
        Duration safety = skew == null ? Duration.ZERO : skew;
        return now.plus(safety).isBefore(expiresAt);
    }
}

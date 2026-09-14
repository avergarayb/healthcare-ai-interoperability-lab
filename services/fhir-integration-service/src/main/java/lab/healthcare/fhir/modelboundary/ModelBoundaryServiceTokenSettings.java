package lab.healthcare.fhir.modelboundary;

import org.springframework.core.env.Environment;
import org.springframework.stereotype.Component;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;

/**
 * Laboratory shared secret for {@code GET /api/model-boundary/v1}. Blank means
 * the HTTP surface is fail-closed. The value is never logged.
 */
@Component
public class ModelBoundaryServiceTokenSettings {

    public static final String PROPERTY = "MODEL_BOUNDARY_SERVICE_TOKEN";
    public static final String HEADER = "X-Service-Token";
    public static final String TEST_DUMMY = "test-model-boundary-token";

    private final String expected;

    public ModelBoundaryServiceTokenSettings(Environment environment) {
        if (environment == null) {
            throw new IllegalArgumentException("Environment must be provided");
        }
        String value = environment.getProperty(PROPERTY, "");
        this.expected = value == null ? "" : value.trim();
    }

    public boolean configured() {
        return !expected.isEmpty();
    }

    public boolean matches(String presented) {
        if (!configured() || presented == null || presented.isBlank()) {
            return false;
        }
        byte[] left = expected.getBytes(StandardCharsets.UTF_8);
        byte[] right = presented.trim().getBytes(StandardCharsets.UTF_8);
        return MessageDigest.isEqual(left, right);
    }
}

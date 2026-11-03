package lab.healthcare.fhir.clinicalread;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.junit.jupiter.api.condition.EnabledIfSystemProperties;
import org.junit.jupiter.api.condition.EnabledIfSystemProperty;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.core.env.Environment;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.file.Path;
import java.time.Duration;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Opt-in compatibility boundary for a test-owned HAPI R4 server seeded with
 * {@code syn-demo-patient-102}. It is intentionally excluded from normal and
 * federation test execution.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@EnabledIfEnvironmentVariable(named = "HAPI_LEGACY_LIVE_IT", matches = "true")
@EnabledIfSystemProperties({
    @EnabledIfSystemProperty(named = "hapi.legacy.profile.enabled", matches = "true"),
    @EnabledIfSystemProperty(named = "hapi.legacy.testOwnedConfirmed", matches = "true")
})
class LegacyHapiClinicalReadCompatibilityLiveIT {

    private static final String READ_TOKEN = "legacy-hapi-clinical-read-test";

    @DynamicPropertySource
    static void legacyHapi(DynamicPropertyRegistry registry) {
        String baseUrl = requiredTestOwnedHapiUrl();
        registry.add("server.port", () -> "0");
        registry.add(
                "spring.autoconfigure.exclude",
                () -> "org.springframework.boot.autoconfigure.jdbc.DataSourceAutoConfiguration");
        registry.add("clinical-read.source", () -> "local-hapi");
        registry.add("fhir.active-server", () -> "local-hapi");
        registry.add("fhir.servers.local-hapi.enabled", () -> "true");
        registry.add("fhir.servers.local-hapi.base-url", () -> baseUrl);
        registry.add("MODEL_BOUNDARY_SERVICE_TOKEN", () -> READ_TOKEN);
        registry.add(
                "federation.security-audit.store-path",
                () -> Path.of(
                                System.getProperty("java.io.tmpdir"),
                                "legacy-hapi-live-audit-" + System.nanoTime() + ".sqlite")
                        .toString());
    }

    @LocalServerPort
    private int port;

    @Autowired
    private Environment environment;

    private final ObjectMapper json = new ObjectMapper();
    private final HttpClient http = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(2)).build();

    @Test
    void localHapiClinicalReadContractRemainsCompatibleWithSeededSyntheticPatient() throws Exception {
        assertThat(environment.getProperty("clinical-read.source")).isEqualTo("local-hapi");
        String base = "http://127.0.0.1:" + port;

        HttpResponse<String> previous = get(base + "/api/clinical-read/v1/patients/MHS-PAT-001");
        assertThat(previous.statusCode()).isIn(200, 404, 503);
        assertThat(previous.body()).doesNotContain("clinical-federation-v1");
        if (previous.statusCode() == 200) {
            assertThat(json.readTree(previous.body()).path("contractVersion").asText())
                    .isEqualTo("clinical-read-v1");
            assertThat(json.readTree(previous.body()).path("destination").asText())
                    .isEqualTo("local-hapi");
        }

        HttpResponse<String> present = get(
                base + "/api/clinical-read/v1/patients/syn-demo-patient-102");
        assertThat(present.statusCode()).isEqualTo(200);
        JsonNode read = json.readTree(present.body());
        assertThat(read.path("contractVersion").asText()).isEqualTo("clinical-read-v1");
        assertThat(read.path("destination").asText()).isEqualTo("local-hapi");
        assertThat(read.path("resource").path("resourceType").asText()).isEqualTo("Patient");
        assertThat(read.path("resource").path("id").asText()).isEqualTo("syn-demo-patient-102");
        assertThat(present.body()).doesNotContain("clinical-federation-v1");
    }

    private HttpResponse<String> get(String url) throws Exception {
        HttpRequest request = HttpRequest.newBuilder(URI.create(url))
                .timeout(Duration.ofSeconds(20))
                .header("X-Service-Token", READ_TOKEN)
                .GET()
                .build();
        return http.send(request, HttpResponse.BodyHandlers.ofString());
    }

    private static String requiredTestOwnedHapiUrl() {
        if (!"true".equals(System.getenv("HAPI_LEGACY_TEST_OWNED"))) {
            throw new IllegalStateException(
                    "HAPI_LEGACY_TEST_OWNED=true is required; never target an operator-owned HAPI server");
        }
        String value = System.getenv("HAPI_LEGACY_BASE_URL");
        if (value == null || value.isBlank()) {
            throw new IllegalStateException("HAPI_LEGACY_BASE_URL is required");
        }
        URI uri = URI.create(value);
        if (!Set.of("http", "https").contains(uri.getScheme())
                || !Set.of("127.0.0.1", "localhost").contains(uri.getHost())
                || uri.getPort() < 1) {
            throw new IllegalStateException(
                    "HAPI_LEGACY_BASE_URL must be an explicit loopback URL with a dedicated port");
        }
        return value;
    }
}

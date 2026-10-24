package lab.healthcare.fhir.federation;

import lab.healthcare.minihis.MiniHisSimulatorApplication;
import lab.healthcare.minilis.MiniLisApplication;

import ca.uhn.fhir.context.FhirContext;
import ca.uhn.fhir.parser.StrictErrorHandler;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.hl7.fhir.r4.model.Resource;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestInstance;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.core.env.Environment;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.testcontainers.containers.PostgreSQLContainer;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.file.Path;
import java.time.Duration;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
class FederationFlowTest {

    private static final String LIS_TOKEN = "lis-federation-token";
    private static final String HIS_EXCHANGE_TOKEN = "his-federation-exchange";
    private static final String HIS_FEDERATION_TOKEN = "his-federation-read";
    private static final String LIS_FEDERATION_TOKEN = "lis-federation-read";
    private static final String CLINIC_TOKEN = "clinic-federation-token";
    private static final String READ_TOKEN = "federation-clinical-read-test";

    private static PostgreSQLContainer<?> postgres;
    private static ConfigurableApplicationContext lis;
    private static ConfigurableApplicationContext his;
    private static String lisUrl;
    private static String hisUrl;

    @DynamicPropertySource
    static void laboratory(DynamicPropertyRegistry registry) {
        startSystems();
        registry.add("server.port", () -> "0");
        registry.add(
                "spring.autoconfigure.exclude",
                () -> "org.springframework.boot.autoconfigure.jdbc.DataSourceAutoConfiguration");
        registry.add("exchange.store-path", () -> Path.of(System.getProperty("java.io.tmpdir"), "federation-flow-" + System.nanoTime() + ".sqlite").toString());
        registry.add("exchange.connectors.mini-lis.base-url", () -> lisUrl);
        registry.add("exchange.connectors.mini-lis.service-token", () -> LIS_TOKEN);
        registry.add("exchange.participants.mini-his.service-token", () -> HIS_EXCHANGE_TOKEN);
        registry.add("exchange.participants.mini-lis.service-token", () -> LIS_TOKEN);
        registry.add("clinical-read.mini-his.base-url", () -> hisUrl);
        registry.add("clinical-read.mini-lis.base-url", () -> lisUrl);
        registry.add("clinical-read.mini-lis.service-token", () -> LIS_TOKEN);
        registry.add("interop.sources.mini-his.base-url", () -> hisUrl);
        registry.add("interop.sources.mini-lis.base-url", () -> lisUrl);
        registry.add("interop.sources.clinic-b.organization-id", () -> "org-clinic-b");
        registry.add("interop.sources.clinic-b.display-name", () -> "Clinic B");
        registry.add("interop.sources.clinic-b.base-url", () -> "http://127.0.0.1:9");
        registry.add("interop.sources.clinic-b.capabilities[0]", () -> "service-request");
        registry.add("federation.participants.mini-his.service-token", () -> HIS_FEDERATION_TOKEN);
        registry.add("federation.participants.mini-lis.service-token", () -> LIS_FEDERATION_TOKEN);
        registry.add("federation.participants.clinic-b.service-token", () -> CLINIC_TOKEN);
        registry.add(
                "federation.security-audit.store-path",
                () -> Path.of(
                                System.getProperty("java.io.tmpdir"),
                                "federation-security-audit-" + System.nanoTime() + ".sqlite")
                        .toString());
        registry.add("federation.grants.mini-his[0]", () -> "mini-his");
        registry.add("federation.grants.mini-his[1]", () -> "mini-lis");
        registry.add("federation.grants.mini-his[2]", () -> "clinic-b");
        registry.add("MODEL_BOUNDARY_SERVICE_TOKEN", () -> READ_TOKEN);
    }

    @LocalServerPort
    private int federationPort;

    @Autowired
    private Environment environment;

    private final ObjectMapper json = new ObjectMapper();
    private final HttpClient http = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(2)).build();

    @AfterAll
    void stop() {
        if (his != null) {
            his.close();
        }
        if (lis != null) {
            lis.close();
        }
        if (postgres != null) {
            postgres.stop();
        }
    }

    @Test
    void twoRealSystemsReturnOneFederatedContext() throws Exception {
        assertThat(environment.getProperty("clinical-read.source")).isEqualTo("local-hapi");
        String base = "http://127.0.0.1:" + federationPort;
        JsonNode accepted = post(base + "/api/exchange/v1/orders", HIS_EXCHANGE_TOKEN, """
                {"sourceOrganizationId":"org-mini-his","destinationSystemKey":"mini-lis","externalRequestId":"FED-ORDER-001","testCode":"GLU","testDescription":"Glucose","requestedAt":"2026-03-01T10:00:00Z","patient":{"identifierSystem":"https://lab.local/mini-his/patient","identifierValue":"MHS-PAT-001","familyName":"Quispe","givenName":"Ana","birthDate":"1984-03-12","administrativeSex":"female"}}
                """);
        String lisOrderId = accepted.path("destination").path("orderId").asText();
        assertThat(lisOrderId).isNotBlank();
        post(lisUrl + "/orders/" + lisOrderId + "/results", LIS_TOKEN, """
                {"externalResultId":"EXT-RES-FED","testCode":"GLU","value":"141","unit":"mmol/L","referenceRange":"70-110","resultedAt":"2026-03-01T12:00:00Z","status":"FINAL"}
                """);

        JsonNode federated = post(base + "/api/clinical-federation/v1/context", HIS_FEDERATION_TOKEN, context(
                "org-mini-his", "mini-his", "https://lab.local/mini-his/patient", "MHS-PAT-001",
                "[\"mini-his\",\"mini-lis\"]"));
        assertThat(federated.path("contractVersion").asText()).isEqualTo("clinical-federation-v1");
        assertThat(federated.path("status").asText()).isEqualTo("complete");
        assertThat(federated.path("callerSystem").asText()).isEqualTo("mini-his");
        assertThat(outcome(federated, "mini-his")).isEqualTo("complete");
        assertThat(outcome(federated, "mini-lis")).isEqualTo("complete");
        assertThat(count(federated, "mini-his", "Patient")).isEqualTo(1);
        assertThat(count(federated, "mini-lis", "Patient")).isEqualTo(1);
        assertThat(count(federated, "mini-his", "Observation")).isGreaterThanOrEqualTo(1);
        assertThat(count(federated, "mini-lis", "Observation")).isGreaterThanOrEqualTo(1);
        assertThat(count(federated, "mini-lis", "ServiceRequest")).isEqualTo(1);
        assertThat(values(federated, "mini-his")).contains("13.4");
        assertThat(values(federated, "mini-lis")).contains("141");
        assertThat(fullUrls(federated)).doesNotHaveDuplicates();
        JsonNode hisObservation = firstObservation(federated, "mini-his", "13.4");
        JsonNode lisObservation = firstObservation(federated, "mini-lis", "141");
        assertThat(hisObservation.path("resource").path("meta").path("source").asText()).isEqualTo("https://lab.local/mini-his");
        assertThat(lisObservation.path("resource").path("meta").path("source").asText()).isEqualTo("https://lab.local/mini-lis");
        assertThat(hisObservation.path("fullUrl").asText()).startsWith(hisUrl + "/Observation/");
        assertThat(lisObservation.path("fullUrl").asText()).startsWith(lisUrl + "/Observation/");
        assertThat(lisObservation.path("resource").path("subject").path("reference").asText()).startsWith(lisUrl + "/Patient/");
        assertThat(lisObservation.path("resource").path("valueQuantity").path("unit").asText()).isEqualTo("mmol/L");
        assertThat(lisObservation.path("resource").path("valueQuantity").has("system")).isFalse();
        assertThat(lisObservation.path("resource").path("code").toString()).doesNotContain("loinc");
        assertThat(hisObservation.path("resource").path("valueQuantity").path("unit").asText()).isEqualTo("g/dL");
        parseAll(federated);

        JsonNode partial = post(base + "/api/clinical-federation/v1/context", HIS_FEDERATION_TOKEN, context(
                "org-mini-his", "mini-his", "https://lab.local/mini-his/patient", "MHS-PAT-002",
                "[\"mini-his\",\"mini-lis\"]"));
        assertThat(partial.path("status").asText()).isEqualTo("partial");
        assertThat(outcome(partial, "mini-his")).isEqualTo("complete");
        assertThat(outcome(partial, "mini-lis")).isEqualTo("identity_unresolved");
        assertThat(count(partial, "mini-lis", "Observation")).isZero();
        assertThat(partial.toString()).doesNotContain("141");

        JsonNode missingConnector = post(base + "/api/clinical-federation/v1/context", HIS_FEDERATION_TOKEN, context(
                "org-mini-his", "mini-his", "https://lab.local/mini-his/patient", "MHS-PAT-001",
                "[\"mini-his\",\"clinic-b\"]"));
        assertThat(missingConnector.path("status").asText()).isEqualTo("partial");
        assertThat(outcome(missingConnector, "clinic-b")).isEqualTo("connector_unavailable");
        assertThat(count(missingConnector, "clinic-b", "Patient")).isZero();

        HttpResponse<String> forbidden = send(base + "/api/clinical-federation/v1/context", CLINIC_TOKEN, context(
                "org-clinic-b", "clinic-b", "https://lab.local/clinic-b/patient", "CLINIC-PAT-001",
                "[\"mini-lis\"]"));
        assertThat(forbidden.statusCode()).isEqualTo(403);
        assertThat(forbidden.body()).contains("source_not_authorized").doesNotContain("13.4").doesNotContain("141");

        HttpResponse<String> anonymous = send(base + "/api/clinical-federation/v1/context", null, context(
                "org-mini-his", "mini-his", "https://lab.local/mini-his/patient", "MHS-PAT-001",
                "[\"mini-his\"]"));
        assertThat(anonymous.statusCode()).isEqualTo(401);
        assertThat(anonymous.body()).doesNotContain("13.4");

        HttpResponse<String> previous = send(
                base + "/api/clinical-read/v1/patients/MHS-PAT-001", READ_TOKEN, null);
        assertThat(previous.statusCode()).isIn(200, 404, 503);
        assertThat(previous.body()).doesNotContain("clinical-federation-v1");
        if (previous.statusCode() == 200) {
            assertThat(json.readTree(previous.body()).path("contractVersion").asText()).isEqualTo("clinical-read-v1");
            assertThat(json.readTree(previous.body()).path("destination").asText()).isEqualTo("local-hapi");
        }

        HttpResponse<String> present = send(
                base + "/api/clinical-read/v1/patients/syn-demo-patient-102", READ_TOKEN, null);
        assertThat(present.statusCode()).isEqualTo(200);
        JsonNode read = json.readTree(present.body());
        assertThat(read.path("contractVersion").asText()).isEqualTo("clinical-read-v1");
        assertThat(read.path("destination").asText()).isEqualTo("local-hapi");
        assertThat(read.path("resource").path("resourceType").asText()).isEqualTo("Patient");
        assertThat(read.path("resource").path("id").asText()).isEqualTo("syn-demo-patient-102");
        assertThat(present.body()).doesNotContain("clinical-federation-v1");
    }

    private static void startSystems() {
        if (lis != null) {
            return;
        }
        postgres = new PostgreSQLContainer<>("postgres:16-alpine");
        postgres.start();
        SpringApplication lisApplication = new SpringApplication(MiniLisApplication.class);
        lisApplication.setDefaultProperties(Map.of(
                "server.port", "0",
                "server.address", "127.0.0.1",
                "spring.main.banner-mode", "off",
                "spring.datasource.url", postgres.getJdbcUrl(),
                "spring.datasource.username", postgres.getUsername(),
                "spring.datasource.password", postgres.getPassword(),
                "mini-lis.service-token", LIS_TOKEN));
        lis = lisApplication.run("--server.port=0", "--server.address=127.0.0.1");
        lisUrl = "http://127.0.0.1:" + lis.getEnvironment().getProperty("local.server.port");

        Path database = Path.of(System.getProperty("java.io.tmpdir"), "mini-his-federation-" + System.nanoTime() + ".sqlite");
        SpringApplication hisApplication = new SpringApplication(MiniHisSimulatorApplication.class);
        hisApplication.setDefaultProperties(Map.of(
                "server.port", "0",
                "server.address", "127.0.0.1",
                "spring.main.banner-mode", "off",
                "mini-his.sqlite-path", database.toString(),
                "mini-his.organization-id", "org-mini-his"));
        his = hisApplication.run("--server.port=0", "--server.address=127.0.0.1");
        hisUrl = "http://127.0.0.1:" + his.getEnvironment().getProperty("local.server.port");
    }

    private JsonNode post(String url, String token, String body) throws Exception {
        HttpResponse<String> response = send(url, token, body);
        assertThat(response.statusCode()).isBetween(200, 299);
        return json.readTree(response.body());
    }

    private HttpResponse<String> send(String url, String token, String body) throws Exception {
        HttpRequest.Builder request = HttpRequest.newBuilder(URI.create(url)).timeout(Duration.ofSeconds(20));
        if (token != null) {
            request.header("X-Service-Token", token);
        }
        if (body == null) {
            request.GET();
        } else {
            request.header("Content-Type", "application/json").POST(HttpRequest.BodyPublishers.ofString(body));
        }
        return http.send(request.build(), HttpResponse.BodyHandlers.ofString());
    }

    private static String context(String organizationId, String systemKey, String identifierSystem, String identifierValue, String sources) {
        return """
                {"requestingOrganizationId":"%s","correlationId":"FED-FLOW-0001","patient":{"systemKey":"%s","identifierSystem":"%s","identifierValue":"%s"},"sources":%s,"resourceTypes":["Patient","Encounter","Observation","Appointment","ServiceRequest","DiagnosticReport"]}
                """.formatted(organizationId, systemKey, identifierSystem, identifierValue, sources);
    }

    private static void parseAll(JsonNode body) {
        var parser = FhirContext.forR4().newJsonParser();
        parser.setParserErrorHandler(new StrictErrorHandler());
        body.path("entries").forEach(entry -> {
            Resource resource = (Resource) parser.parseResource(entry.path("resource").toString());
            assertThat(resource.getResourceType().name()).isEqualTo(entry.path("resource").path("resourceType").asText());
        });
    }

    private static String outcome(JsonNode body, String source) {
        for (JsonNode item : body.path("sources")) {
            if (source.equals(item.path("sourceKey").asText())) {
                return item.path("outcome").asText();
            }
        }
        return "";
    }

    private static int count(JsonNode body, String source, String type) {
        int found = 0;
        for (JsonNode entry : body.path("entries")) {
            if (source.equals(entry.path("sourceKey").asText())
                    && type.equals(entry.path("resource").path("resourceType").asText())) {
                found++;
            }
        }
        return found;
    }

    private static Set<String> values(JsonNode body, String source) {
        Set<String> found = new HashSet<>();
        for (JsonNode entry : body.path("entries")) {
            if (source.equals(entry.path("sourceKey").asText())) {
                JsonNode value = entry.path("resource").path("valueQuantity").path("value");
                if (!value.isMissingNode()) {
                    found.add(value.asText());
                }
            }
        }
        return found;
    }

    private static List<String> fullUrls(JsonNode body) {
        List<String> found = new ArrayList<>();
        body.path("entries").forEach(entry -> found.add(entry.path("fullUrl").asText()));
        return found;
    }

    private static JsonNode firstObservation(JsonNode body, String source, String value) {
        for (JsonNode entry : body.path("entries")) {
            if (source.equals(entry.path("sourceKey").asText())
                    && "Observation".equals(entry.path("resource").path("resourceType").asText())
                    && value.equals(entry.path("resource").path("valueQuantity").path("value").asText())) {
                return entry;
            }
        }
        throw new AssertionError("Missing observation " + source + " " + value);
    }
}

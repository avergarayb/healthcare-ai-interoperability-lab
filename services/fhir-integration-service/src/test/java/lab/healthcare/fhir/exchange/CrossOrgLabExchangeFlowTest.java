package lab.healthcare.fhir.exchange;

import lab.healthcare.minihis.MiniHisSimulatorApplication;
import lab.healthcare.minilis.MiniLisApplication;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestInstance;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.testcontainers.containers.PostgreSQLContainer;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.file.Path;
import java.time.Duration;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
class CrossOrgLabExchangeFlowTest {

    private static final String LIS_TOKEN = "lis-flow-token";
    private static final String HIS_TOKEN = "his-flow-token";
    private static final String CLINIC_TOKEN = "clinic-flow-token";
    private static final String READ_TOKEN = "exchange-clinical-read-test";

    private static PostgreSQLContainer<?> postgres;
    private static ConfigurableApplicationContext lis;
    private static String lisUrl;

    @DynamicPropertySource
    static void laboratory(DynamicPropertyRegistry registry) {
        startLaboratory();
        registry.add("server.port", () -> "0");
        registry.add(
                "spring.autoconfigure.exclude",
                () -> "org.springframework.boot.autoconfigure.jdbc.DataSourceAutoConfiguration");
        registry.add("exchange.store-path", () -> Path.of(System.getProperty("java.io.tmpdir"), "exchange-flow-" + System.nanoTime() + ".sqlite").toString());
        registry.add("exchange.connectors.mini-lis.base-url", () -> lisUrl);
        registry.add("exchange.connectors.mini-lis.service-token", () -> LIS_TOKEN);
        registry.add("exchange.participants.mini-his.service-token", () -> HIS_TOKEN);
        registry.add("exchange.participants.clinic-b.service-token", () -> CLINIC_TOKEN);
        registry.add("clinical-read.source", () -> "mini-lis");
        registry.add("clinical-read.mini-lis.base-url", () -> lisUrl);
        registry.add("clinical-read.mini-lis.service-token", () -> LIS_TOKEN);
        registry.add("MODEL_BOUNDARY_SERVICE_TOKEN", () -> READ_TOKEN);
        registry.add("interop.sources.clinic-b.organization-id", () -> "org-clinic-b");
        registry.add("interop.sources.clinic-b.display-name", () -> "Clinic B");
        registry.add("interop.sources.clinic-b.base-url", () -> "http://127.0.0.1:9");
        registry.add("interop.sources.clinic-b.capabilities[0]", () -> "service-request");
    }

    @LocalServerPort
    private int exchangePort;

    private ConfigurableApplicationContext his;
    private final ObjectMapper json = new ObjectMapper();
    private final HttpClient http = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(2)).build();

    @BeforeAll
    void startHospital() {
        Path database = Path.of(System.getProperty("java.io.tmpdir"), "mini-his-exchange-" + System.nanoTime() + ".sqlite");
        SpringApplication application = new SpringApplication(MiniHisSimulatorApplication.class);
        application.setDefaultProperties(Map.of(
                "server.port", "0",
                "server.address", "127.0.0.1",
                "spring.main.banner-mode", "off",
                "mini-his.sqlite-path", database.toString(),
                "mini-his.organization-id", "org-mini-his",
                "mini-his.exchange.base-url", "http://127.0.0.1:" + exchangePort,
                "mini-his.exchange.service-token", HIS_TOKEN));
        his = application.run("--server.port=0", "--server.address=127.0.0.1");
    }

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
    void orderTravelsFromMiniHisThroughJavaToMiniLisAndTheResultReturns() throws Exception {
        assertThat(his.getEnvironment().getProperty("mini-his.exchange.base-url")).doesNotContain(lisPort());
        String hisBase = "http://127.0.0.1:" + his.getEnvironment().getProperty("local.server.port");
        JsonNode created = send("POST", hisBase + "/lab-orders", """
                {"patientId":"MHS-PAT-001","destinationSystemKey":"mini-lis","testCode":"GLU","testDescription":"Glucose","requestedAt":"2026-03-01T10:00:00Z"}
                """, null);
        String orderId = created.path("orderId").asText();
        JsonNode submitted = send("POST", hisBase + "/lab-orders/" + orderId + "/submission", null, null);
        String lisOrderId = submitted.path("destination").path("orderId").asText();
        String correlationId = submitted.path("correlationId").asText();
        assertThat(submitted.path("serviceRequest").path("resourceType").asText()).isEqualTo("ServiceRequest");
        assertThat(submitted.path("serviceRequest").toString()).doesNotContain("loinc").doesNotContain("Quispe");
        assertThat(identifier(submitted.path("serviceRequest"), "https://lab.local/exchange/service-request")).isEqualTo(correlationId);
        assertThat(identifier(submitted.path("serviceRequest"), "https://lab.local/org-mini-his/service-request")).isEqualTo(orderId);

        JsonNode repeated = send("POST", hisBase + "/lab-orders/" + orderId + "/submission", null, null);
        assertThat(repeated.path("deliveryState").asText()).isEqualTo("duplicate");
        assertThat(repeated.path("destination").path("orderId").asText()).isEqualTo(lisOrderId);
        JsonNode stored = send(
                "GET",
                lisUrl + "/orders?requestingOrganizationId=org-mini-his&externalRequestId=" + orderId,
                null,
                LIS_TOKEN);
        assertThat(stored.path("orderId").asText()).isEqualTo(lisOrderId);

        JsonNode beforeResults = send("GET", hisBase + "/lab-orders/" + orderId + "/results", null, null);
        assertThat(beforeResults.path("correlationId").asText()).isEqualTo(correlationId);
        assertThat(beforeResults.path("observations")).isEmpty();
        assertThat(beforeResults.path("diagnosticReport").path("resourceType").asText()).isEqualTo("DiagnosticReport");
        assertThat(beforeResults.path("diagnosticReport").path("result")).isEmpty();
        assertThat(beforeResults.toString()).doesNotContain("141");

        send("POST", lisUrl + "/orders/" + lisOrderId + "/results", """
                {"externalResultId":"EXT-RES-FLOW","testCode":"GLU","value":"141","unit":"mmol/L","referenceRange":"70-110","resultedAt":"2026-03-01T12:00:00Z","status":"FINAL"}
                """, LIS_TOKEN);
        JsonNode results = send("GET", hisBase + "/lab-orders/" + orderId + "/results", null, null);
        assertThat(results.path("correlationId").asText()).isEqualTo(correlationId);
        assertThat(results.path("destination").path("orderId").asText()).isEqualTo(lisOrderId);
        assertThat(results.path("observations").get(0).path("valueQuantity").path("value").asText()).isEqualTo("141");
        assertThat(results.path("observations").get(0).path("valueQuantity").path("unit").asText()).isEqualTo("mmol/L");
        assertThat(results.path("observations").get(0).path("valueQuantity").has("system")).isFalse();
        assertThat(results.path("observations").get(0).path("basedOn").get(0).path("reference").asText())
                .isEqualTo("ServiceRequest/" + lisOrderId);
        assertThat(results.toString()).doesNotContain("loinc").doesNotContain("ucum");

        JsonNode clinicalRead = send(
                "GET",
                "http://127.0.0.1:" + exchangePort + "/api/clinical-read/v1/diagnostic-reports/" + lisOrderId,
                null,
                READ_TOKEN);
        assertThat(clinicalRead.path("destination").asText()).isEqualTo("mini-lis");
        assertThat(clinicalRead.path("resource").path("result").get(0).path("reference").asText())
                .startsWith("Observation/");

        HttpResponse<String> forbidden = http.send(
                HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + exchangePort + "/api/exchange/v1/orders/" + orderId + "/report"))
                        .header("X-Service-Token", CLINIC_TOKEN)
                        .GET()
                        .build(),
                HttpResponse.BodyHandlers.ofString());
        assertThat(forbidden.statusCode()).isEqualTo(404);
        assertThat(forbidden.body()).doesNotContain("141");

        HttpResponse<String> spoofed = http.send(
                HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + exchangePort + "/api/exchange/v1/orders"))
                        .header("Content-Type", "application/json")
                        .header("X-Service-Token", CLINIC_TOKEN)
                        .POST(HttpRequest.BodyPublishers.ofString("""
                                {"sourceOrganizationId":"org-mini-his","destinationSystemKey":"mini-lis","externalRequestId":"CLINIC-SPOOF-001","testCode":"GLU","testDescription":"Glucose","requestedAt":"2026-03-01T10:00:00Z","patient":{"identifierSystem":"https://lab.local/mini-his/patient","identifierValue":"MHS-PAT-001","familyName":"Quispe","givenName":"Ana","birthDate":"1984-03-12","administrativeSex":"female"}}
                                """))
                        .build(),
                HttpResponse.BodyHandlers.ofString());
        assertThat(spoofed.statusCode()).isEqualTo(403);
        assertThat(spoofed.body()).contains("organization_forbidden").doesNotContain("141");
        HttpResponse<String> absent = http.send(
                HttpRequest.newBuilder(URI.create(lisUrl + "/orders?requestingOrganizationId=org-mini-his&externalRequestId=CLINIC-SPOOF-001"))
                        .header("X-Service-Token", LIS_TOKEN)
                        .GET()
                        .build(),
                HttpResponse.BodyHandlers.ofString());
        assertThat(absent.statusCode()).isEqualTo(404);
    }

    private static void startLaboratory() {
        if (lis != null) {
            return;
        }
        postgres = new PostgreSQLContainer<>("postgres:16-alpine");
        postgres.start();
        SpringApplication application = new SpringApplication(MiniLisApplication.class);
        application.setDefaultProperties(Map.of(
                "server.port", "0",
                "server.address", "127.0.0.1",
                "spring.main.banner-mode", "off",
                "spring.datasource.url", postgres.getJdbcUrl(),
                "spring.datasource.username", postgres.getUsername(),
                "spring.datasource.password", postgres.getPassword(),
                "mini-lis.service-token", LIS_TOKEN));
        lis = application.run("--server.port=0", "--server.address=127.0.0.1");
        lisUrl = "http://127.0.0.1:" + lis.getEnvironment().getProperty("local.server.port");
    }

    private JsonNode send(String method, String url, String body, String token) throws Exception {
        HttpRequest.Builder request = HttpRequest.newBuilder(URI.create(url)).timeout(Duration.ofSeconds(5));
        if (token != null) {
            request.header("X-Service-Token", token);
        }
        if ("POST".equals(method)) {
            request.header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString(body == null ? "" : body));
        } else {
            request.GET();
        }
        HttpResponse<String> response = http.send(request.build(), HttpResponse.BodyHandlers.ofString());
        assertThat(response.statusCode()).isBetween(200, 299);
        return json.readTree(response.body());
    }

    private static String identifier(JsonNode resource, String system) {
        for (JsonNode identifier : resource.path("identifier")) {
            if (system.equals(identifier.path("system").asText())) {
                return identifier.path("value").asText();
            }
        }
        return null;
    }

    private static String lisPort() {
        return lisUrl.substring(lisUrl.lastIndexOf(':') + 1);
    }
}

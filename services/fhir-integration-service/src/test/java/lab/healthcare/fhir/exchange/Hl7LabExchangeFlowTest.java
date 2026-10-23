package lab.healthcare.fhir.exchange;

import lab.healthcare.minihis.MiniHisSimulatorApplication;
import lab.healthcare.minilis.Hl7Server;
import lab.healthcare.minilis.MiniLisApplication;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestInstance;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Qualifier;
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
class Hl7LabExchangeFlowTest {

    private static final String LIS_TOKEN = "lis-hl7-flow-token";
    private static final String HIS_TOKEN = "his-hl7-flow-token";
    private static final String CLINIC_TOKEN = "clinic-hl7-flow-token";
    private static final String READ_TOKEN = "hl7-clinical-read-test";
    private static final String SECRET = "hl7-flow-secret";

    private static PostgreSQLContainer<?> postgres;
    private static ConfigurableApplicationContext lis;
    private static String lisUrl;
    private static int lisHl7Port;

    @DynamicPropertySource
    static void laboratory(DynamicPropertyRegistry registry) {
        startLaboratory();
        registry.add("server.port", () -> "0");
        registry.add("spring.autoconfigure.exclude", () -> "org.springframework.boot.autoconfigure.jdbc.DataSourceAutoConfiguration");
        registry.add("exchange.store-path", () -> Path.of(System.getProperty("java.io.tmpdir"), "exchange-hl7-" + System.nanoTime() + ".sqlite").toString());
        registry.add("exchange.connectors.mini-lis.protocol", () -> "hl7v2");
        registry.add("exchange.connectors.mini-lis.hl7.host", () -> "127.0.0.1");
        registry.add("exchange.connectors.mini-lis.hl7.port", () -> Integer.toString(lisHl7Port));
        registry.add("exchange.connectors.mini-lis.hl7.shared-secret", () -> SECRET);
        registry.add("exchange.connectors.mini-lis.hl7.listen-port", () -> "0");
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

    @Autowired
    @Qualifier("miniLisOrderDestination")
    private MiniLisHl7ExchangeConnector destination;

    private ConfigurableApplicationContext his;
    private final ObjectMapper json = new ObjectMapper();
    private final HttpClient http = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(2)).build();

    @BeforeAll
    void startHospital() throws Exception {
        Path database = Path.of(System.getProperty("java.io.tmpdir"), "mini-his-hl7-" + System.nanoTime() + ".sqlite");
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
        int resultPort = destination.listenPort();
        HttpResponse<String> peer = http.send(
                HttpRequest.newBuilder(URI.create(lisUrl + "/hl7/result-peer"))
                        .header("Content-Type", "application/json")
                        .header("X-Service-Token", LIS_TOKEN)
                        .PUT(HttpRequest.BodyPublishers.ofString("{\"host\":\"127.0.0.1\",\"port\":" + resultPort + "}"))
                        .build(),
                HttpResponse.BodyHandlers.ofString());
        assertThat(peer.statusCode()).isEqualTo(200);
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
    void anOrderTravelsAsOmlAndTheResultReturnsAsOru() throws Exception {
        String hisBase = "http://127.0.0.1:" + his.getEnvironment().getProperty("local.server.port");
        JsonNode created = send("POST", hisBase + "/lab-orders", """
                {"patientId":"MHS-PAT-001","destinationSystemKey":"mini-lis","testCode":"GLU","testDescription":"Glucose","requestedAt":"2026-03-01T10:00:00Z"}
                """, null);
        String orderId = created.path("orderId").asText();
        JsonNode submitted = send("POST", hisBase + "/lab-orders/" + orderId + "/submission", null, null);
        String lisOrderId = submitted.path("destination").path("orderId").asText();
        assertThat(submitted.path("serviceRequest").path("resourceType").asText()).isEqualTo("ServiceRequest");
        assertThat(submitted.path("serviceRequest").toString()).doesNotContain("loinc");
        JsonNode repeated = send("POST", hisBase + "/lab-orders/" + orderId + "/submission", null, null);
        assertThat(repeated.path("deliveryState").asText()).isEqualTo("duplicate");
        assertThat(repeated.path("destination").path("orderId").asText()).isEqualTo(lisOrderId);

        JsonNode before = send("GET", hisBase + "/lab-orders/" + orderId + "/results", null, null);
        assertThat(before.path("observations")).isEmpty();

        send("POST", lisUrl + "/orders/" + lisOrderId + "/results", """
                {"externalResultId":"EXT-RES-HL7-FLOW","testCode":"GLU","value":"141","unit":"mmol/L","referenceRange":"70-110","resultedAt":"2026-03-01T12:00:00Z","status":"FINAL"}
                """, LIS_TOKEN);
        JsonNode restResult = send("GET", lisUrl + "/orders/" + lisOrderId + "/results", null, LIS_TOKEN);
        JsonNode hl7Result = send("GET", hisBase + "/lab-orders/" + orderId + "/results", null, null);
        assertThat(hl7Result.path("observations").get(0).path("valueQuantity").path("value").asText())
                .isEqualTo(restResult.get(0).path("value").asText())
                .isEqualTo("141");
        assertThat(hl7Result.path("observations").get(0).path("valueQuantity").path("unit").asText())
                .isEqualTo(restResult.get(0).path("unit").asText())
                .isEqualTo("mmol/L");
        assertThat(hl7Result.path("observations").get(0).path("valueQuantity").has("system")).isFalse();
        assertThat(hl7Result.path("observations").get(0).path("basedOn").get(0).path("reference").asText())
                .isEqualTo("ServiceRequest/" + lisOrderId);
        assertThat(hl7Result.toString()).doesNotContain("loinc").doesNotContain("ucum");

        JsonNode clinicalRead = send(
                "GET",
                "http://127.0.0.1:" + exchangePort + "/api/clinical-read/v1/diagnostic-reports/" + lisOrderId,
                null,
                READ_TOKEN);
        assertThat(clinicalRead.path("destination").asText()).isEqualTo("mini-lis");
        HttpResponse<String> forbidden = http.send(
                HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + exchangePort + "/api/exchange/v1/orders/" + orderId + "/report"))
                        .header("X-Service-Token", CLINIC_TOKEN)
                        .GET()
                        .build(),
                HttpResponse.BodyHandlers.ofString());
        assertThat(forbidden.statusCode()).isEqualTo(404);
        assertThat(forbidden.body()).doesNotContain("141");
    }

    @Test
    void aLostResultPublicationCanBeRetriedWithoutASecondObservation() throws Exception {
        int deadPort;
        try (java.net.ServerSocket closed = new java.net.ServerSocket()) {
            closed.bind(new java.net.InetSocketAddress("127.0.0.1", 0));
            deadPort = closed.getLocalPort();
        }
        try {
        HttpResponse<String> moved = http.send(
                HttpRequest.newBuilder(URI.create(lisUrl + "/hl7/result-peer"))
                        .header("Content-Type", "application/json")
                        .header("X-Service-Token", LIS_TOKEN)
                        .PUT(HttpRequest.BodyPublishers.ofString("{\"host\":\"127.0.0.1\",\"port\":" + deadPort + "}"))
                        .build(),
                HttpResponse.BodyHandlers.ofString());
        assertThat(moved.statusCode()).isEqualTo(200);
        String hisBase = "http://127.0.0.1:" + his.getEnvironment().getProperty("local.server.port");
        JsonNode created = send("POST", hisBase + "/lab-orders", """
                {"patientId":"MHS-PAT-001","destinationSystemKey":"mini-lis","testCode":"GLU","testDescription":"Glucose","requestedAt":"2026-03-02T10:00:00Z"}
                """, null);
        String orderId = created.path("orderId").asText();
        JsonNode submitted = send("POST", hisBase + "/lab-orders/" + orderId + "/submission", null, null);
        String lisOrderId = submitted.path("destination").path("orderId").asText();
        JsonNode recorded = send("POST", lisUrl + "/orders/" + lisOrderId + "/results", """
                {"externalResultId":"EXT-RES-HL7-RETRY","testCode":"GLU","value":"141","unit":"mmol/L","referenceRange":"70-110","resultedAt":"2026-03-02T12:00:00Z","status":"FINAL"}
                """, LIS_TOKEN);
        JsonNode stored = send("GET", lisUrl + "/orders/" + lisOrderId + "/results", null, LIS_TOKEN);
        assertThat(stored.get(0).path("status").asText()).isEqualTo("FINAL");
        assertThat(stored.get(0).path("value").asText()).isEqualTo("141");
        JsonNode missing = send("GET", hisBase + "/lab-orders/" + orderId + "/results", null, null);
        assertThat(missing.path("observations")).isEmpty();
        HttpResponse<String> restored = http.send(
                HttpRequest.newBuilder(URI.create(lisUrl + "/hl7/result-peer"))
                        .header("Content-Type", "application/json")
                        .header("X-Service-Token", LIS_TOKEN)
                        .PUT(HttpRequest.BodyPublishers.ofString("{\"host\":\"127.0.0.1\",\"port\":" + destination.listenPort() + "}"))
                        .build(),
                HttpResponse.BodyHandlers.ofString());
        assertThat(restored.statusCode()).isEqualTo(200);
        String resultId = recorded.path("resultId").asText();
        JsonNode published = send("POST", lisUrl + "/hl7/results/" + resultId + "/publication", "", LIS_TOKEN);
        assertThat(published.path("ack").asText()).isEqualTo("AA");
        JsonNode once = send("GET", hisBase + "/lab-orders/" + orderId + "/results", null, null);
        assertThat(once.path("observations")).hasSize(1);
        assertThat(once.path("observations").get(0).path("valueQuantity").path("value").asText()).isEqualTo("141");
        JsonNode again = send("POST", lisUrl + "/hl7/results/" + resultId + "/publication", "", LIS_TOKEN);
        assertThat(again.path("ack").asText()).isEqualTo("AA");
        JsonNode twice = send("GET", hisBase + "/lab-orders/" + orderId + "/results", null, null);
        assertThat(twice.path("observations")).hasSize(1);
        assertThat(send("GET", lisUrl + "/results/" + resultId, null, LIS_TOKEN).path("status").asText()).isEqualTo("FINAL");
        } finally {
            http.send(
                    HttpRequest.newBuilder(URI.create(lisUrl + "/hl7/result-peer"))
                            .header("Content-Type", "application/json")
                            .header("X-Service-Token", LIS_TOKEN)
                            .PUT(HttpRequest.BodyPublishers.ofString("{\"host\":\"127.0.0.1\",\"port\":" + destination.listenPort() + "}"))
                            .build(),
                    HttpResponse.BodyHandlers.ofString());
        }
    }

    private static void startLaboratory() {
        if (lis != null) {
            return;
        }
        postgres = new PostgreSQLContainer<>("postgres:16-alpine");
        postgres.start();
        SpringApplication application = new SpringApplication(MiniLisApplication.class);
        java.util.HashMap<String, Object> properties = new java.util.HashMap<>();
        properties.put("server.port", "0");
        properties.put("server.address", "127.0.0.1");
        properties.put("spring.main.banner-mode", "off");
        properties.put("spring.datasource.url", postgres.getJdbcUrl());
        properties.put("spring.datasource.username", postgres.getUsername());
        properties.put("spring.datasource.password", postgres.getPassword());
        properties.put("mini-lis.service-token", LIS_TOKEN);
        properties.put("mini-lis.hl7.enabled", "true");
        properties.put("mini-lis.hl7.port", "0");
        properties.put("mini-lis.hl7.shared-secret", SECRET);
        properties.put("mini-lis.hl7.bind-address", "127.0.0.1");
        application.setDefaultProperties(properties);
        lis = application.run("--server.port=0", "--server.address=127.0.0.1");
        lisUrl = "http://127.0.0.1:" + lis.getEnvironment().getProperty("local.server.port");
        lisHl7Port = lis.getBean(Hl7Server.class).port();
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
        assertThat(response.statusCode()).as(url + " " + response.body()).isBetween(200, 299);
        return json.readTree(response.body());
    }
}

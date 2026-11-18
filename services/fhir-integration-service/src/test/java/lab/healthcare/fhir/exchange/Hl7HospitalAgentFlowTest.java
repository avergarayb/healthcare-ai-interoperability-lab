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
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.testcontainers.containers.PostgreSQLContainer;

import java.io.ByteArrayOutputStream;
import java.net.InetSocketAddress;
import java.net.ServerSocket;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.time.Duration;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Real Mini HIS, FHIR Integration Service, and Mini LIS processes in one JVM,
 * then one Python process for MCP, LangGraph, and Human Review. The provider
 * hop is intercepted. This is not a canned federation envelope.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.DEFINED_PORT)
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
class Hl7HospitalAgentFlowTest {

    private static final String LIS_TOKEN = "lis-hl7-hospital-token";
    private static final String HIS_TOKEN = "his-hl7-hospital-token";
    private static final String FED_TOKEN = "hl7-hospital-federation";
    private static final String READ_TOKEN = "hl7-hospital-read";
    private static final String SECRET = "hl7-hospital-secret";
    private static final String HIS_OBSERVATION = "MHS-RES-001";

    private static PostgreSQLContainer<?> postgres;
    private static ConfigurableApplicationContext lis;
    private static ConfigurableApplicationContext his;
    private static String lisUrl;
    private static String hisUrl;
    private static int lisHl7Port;
    private static int exchangePort;
    private static String storePath;
    private static String auditPath;

    @DynamicPropertySource
    static void laboratory(DynamicPropertyRegistry registry) throws Exception {
        startLaboratory();
        registry.add("server.port", () -> Integer.toString(exchangePort));
        registry.add("server.address", () -> "127.0.0.1");
        registry.add("spring.autoconfigure.exclude", () -> "org.springframework.boot.autoconfigure.jdbc.DataSourceAutoConfiguration");
        registry.add("exchange.store-path", () -> storePath);
        registry.add("exchange.connectors.mini-lis.protocol", () -> "hl7v2");
        registry.add("exchange.connectors.mini-lis.hl7.host", () -> "127.0.0.1");
        registry.add("exchange.connectors.mini-lis.hl7.port", () -> Integer.toString(lisHl7Port));
        registry.add("exchange.connectors.mini-lis.hl7.shared-secret", () -> SECRET);
        registry.add("exchange.connectors.mini-lis.hl7.listen-port", () -> "0");
        registry.add("exchange.participants.mini-his.service-token", () -> HIS_TOKEN);
        registry.add("clinical-read.source", () -> "mini-lis");
        registry.add("clinical-read.mini-his.base-url", () -> hisUrl);
        registry.add("clinical-read.mini-lis.base-url", () -> lisUrl);
        registry.add("clinical-read.mini-lis.service-token", () -> LIS_TOKEN);
        registry.add("interop.sources.mini-his.base-url", () -> hisUrl);
        registry.add("interop.sources.mini-lis.base-url", () -> lisUrl);
        registry.add("federation.participants.mini-his.service-token", () -> FED_TOKEN);
        registry.add("federation.security-audit.store-path", () -> auditPath);
        registry.add("MODEL_BOUNDARY_SERVICE_TOKEN", () -> READ_TOKEN);
    }

    @LocalServerPort
    private int port;

    @Autowired
    @Qualifier("miniLisOrderDestination")
    private MiniLisHl7ExchangeConnector destination;

    private final ObjectMapper json = new ObjectMapper();
    private final HttpClient http = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(2)).build();

    @BeforeAll
    void pointResultPeerAtTheExchange() throws Exception {
        assertThat(port).isEqualTo(exchangePort);
        int resultPort = destination.listenPort();
        assertThat(resultPort).isGreaterThan(0);
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
    void aHospitalOrderReachesTheExistingAgentThroughTheLiveExchange() throws Exception {
        JsonNode created = send("POST", hisUrl + "/lab-orders", """
                {"patientId":"MHS-PAT-001","destinationSystemKey":"mini-lis","testCode":"GLU","testDescription":"Glucose","requestedAt":"2026-11-17T15:00:00Z"}
                """, null);
        String hisOrderId = created.path("orderId").asText();
        JsonNode submitted = send("POST", hisUrl + "/lab-orders/" + hisOrderId + "/submission", null, null);
        String lisOrderId = submitted.path("destination").path("orderId").asText();
        assertThat(submitted.path("serviceRequest").path("resourceType").asText()).isEqualTo("ServiceRequest");
        assertThat(lisOrderId).startsWith("MLS-ORD-");

        JsonNode recorded = send("POST", lisUrl + "/orders/" + lisOrderId + "/results", """
                {"externalResultId":"EXT-RES-HL7-HOSPITAL","testCode":"GLU","value":"90","unit":"mg/dL","referenceRange":"70-110","resultedAt":"2026-11-17T16:00:00Z","status":"FINAL"}
                """, LIS_TOKEN);
        String lisResultId = recorded.path("resultId").asText();
        JsonNode hl7Result = send("GET", hisUrl + "/lab-orders/" + hisOrderId + "/results", null, null);
        JsonNode observation = hl7Result.path("observations").get(0);
        assertThat(observation.path("id").asText()).isEqualTo(lisResultId);
        assertThat(observation.path("valueQuantity").path("value").asText()).isEqualTo("90");
        assertThat(observation.path("valueQuantity").path("system").asText()).isEqualTo("http://unitsofmeasure.org");
        assertThat(observation.path("valueQuantity").path("code").asText()).isEqualTo("mg/dL");
        assertThat(observation.path("basedOn").get(0).path("reference").asText()).isEqualTo("ServiceRequest/" + lisOrderId);
        assertThat(hl7Result.toString()).doesNotContain("MSH|").doesNotContain("loinc");

        JsonNode report = send(
                "GET",
                "http://127.0.0.1:" + exchangePort + "/api/exchange/v1/orders/" + hisOrderId + "/report",
                null,
                HIS_TOKEN);
        assertThat(report.path("serviceRequest").path("resourceType").asText()).isEqualTo("ServiceRequest");
        assertThat(report.path("serviceRequest").path("id").asText()).isEqualTo(hisOrderId);
        assertThat(report.path("diagnosticReport").path("resourceType").asText()).isEqualTo("DiagnosticReport");
        assertThat(report.path("diagnosticReport").path("id").asText()).isEqualTo(lisOrderId);
        assertThat(report.path("diagnosticReport").path("basedOn").get(0).path("reference").asText())
                .isEqualTo("ServiceRequest/" + lisOrderId);
        assertThat(report.path("diagnosticReport").path("result").get(0).path("reference").asText())
                .isEqualTo("Observation/" + lisResultId);
        assertThat(report.toString()).doesNotContain("MSH|");

        List<Map<String, Object>> inbound = lis.getBean(JdbcTemplate.class).queryForList(
                "SELECT message_control_id, ack_code, filler_order_id FROM hl7_inbound_message WHERE placer_order_id = ?",
                hisOrderId);
        assertThat(inbound).hasSize(1);
        assertThat(inbound.get(0).get("ack_code")).isEqualTo("AA");
        assertThat(inbound.get(0).get("filler_order_id")).isEqualTo(lisOrderId);
        String omlControlId = String.valueOf(inbound.get(0).get("message_control_id"));
        assertThat(omlControlId).isNotBlank();

        try (Connection connection = DriverManager.getConnection("jdbc:sqlite:" + storePath.replace('\\', '/'))) {
            try (PreparedStatement statement = connection.prepareStatement(
                    "SELECT destination_order_id, destination_patient_id FROM exchange_order WHERE source_order_id = ?")) {
                statement.setString(1, hisOrderId);
                try (ResultSet rows = statement.executeQuery()) {
                    assertThat(rows.next()).isTrue();
                    assertThat(rows.getString("destination_order_id")).isEqualTo(lisOrderId);
                    assertThat(rows.getString("destination_patient_id")).isNotBlank();
                }
            }
            try (PreparedStatement statement = connection.prepareStatement(
                    "SELECT message_control_id, external_result_id FROM exchange_hl7_result WHERE source_order_id = ?")) {
                statement.setString(1, hisOrderId);
                try (ResultSet rows = statement.executeQuery()) {
                    assertThat(rows.next()).isTrue();
                    assertThat(rows.getString("message_control_id")).isEqualTo(lisResultId);
                    assertThat(rows.getString("external_result_id")).isEqualTo("EXT-RES-HL7-HOSPITAL");
                    assertThat(rows.getString("message_control_id")).isNotEqualTo(omlControlId);
                }
            }
        }

        JsonNode federation = send("POST", "http://127.0.0.1:" + exchangePort + "/api/clinical-federation/v1/context", """
                {"requestingOrganizationId":"org-mini-his","patient":{"systemKey":"mini-his","identifierSystem":"https://lab.local/mini-his/patient","identifierValue":"MHS-PAT-001"},"sources":["mini-his","mini-lis"],"resourceTypes":["Patient","Encounter","Observation","Appointment","ServiceRequest","DiagnosticReport"],"correlationId":"FED-HL7002HOSPITAL1"}
                """, FED_TOKEN);
        assertThat(federation.path("status").asText()).isEqualTo("complete");
        assertThat(federation.path("truncated").asBoolean()).isFalse();
        assertThat(outcomes(federation)).containsEntry("mini-his", "complete").containsEntry("mini-lis", "complete");
        assertThat(federation.toString()).doesNotContain("MSH|").doesNotContain("OML^");
        JsonNode hisFact = entry(federation, "mini-his", "Observation", HIS_OBSERVATION);
        assertThat(hisFact.path("valueQuantity").path("value").decimalValue()).isEqualByComparingTo("13.4");
        assertThat(hisFact.path("valueQuantity").path("system").asText()).isEqualTo("http://unitsofmeasure.org");
        assertThat(hisFact.path("valueQuantity").path("code").asText()).isEqualTo("g/dL");
        JsonNode lisFact = entry(federation, "mini-lis", "Observation", lisResultId);
        assertThat(lisFact.path("valueQuantity").path("value").decimalValue()).isEqualByComparingTo("90");
        assertThat(lisFact.path("valueQuantity").path("system").asText()).isEqualTo("http://unitsofmeasure.org");
        assertThat(lisFact.path("valueQuantity").path("code").asText()).isEqualTo("mg/dL");
        assertThat(lisFact.path("valueQuantity").path("unit").asText()).isEqualTo("mg/dL");

        JsonNode agent = runAgent(lisResultId);
        assertThat(agent.path("ok").asBoolean()).isTrue();
        assertThat(agent.path("phase").asText()).isEqualTo("PENDING_REVIEW");
        assertThat(agent.path("reason").asText()).isEqualTo("pending_human_review");
        assertThat(agent.path("review_status").asText()).isEqualTo("pending");
        assertThat(agent.path("requests_sent").asInt()).isEqualTo(1);
        assertThat(agent.path("model_calls").asInt()).isEqualTo(1);
        assertThat(agent.path("provider_calls").asInt()).isEqualTo(1);
        assertThat(agent.path("provider_hosts").get(0).asText()).isEqualTo("generativelanguage.googleapis.com");
        assertThat(agent.path("replay_reason").asText()).isEqualTo("replay_denied");
        assertThat(agent.path("summary_status").asText()).isEqualTo("pending");
        assertThat(agent.path("decision").asText()).isEqualTo("approved");
        assertThat(agent.path("second_decision").asText()).isEqualTo("already_decided");
        assertThat(agent.path("authorization_id").asText()).isEqualTo("hl7-002-hospital");
        assertThat(agent.path("reservations")).hasSize(1);
        assertThat(agent.path("chart_ids").toString()).contains(HIS_OBSERVATION).contains(lisResultId);
        assertThat(cited(agent, "mini-his", HIS_OBSERVATION)).isTrue();
        assertThat(cited(agent, "mini-lis", lisResultId)).isTrue();
        assertThat(agent.path("queued_audit").toString()).contains("queued");
        assertThat(agent.path("decision_audit").toString()).contains("approved");
        assertThat(agent.toString()).doesNotContain("MSH|").doesNotContain(SECRET);
    }

    private JsonNode runAgent(String lisResultId) throws Exception {
        Path cwd = Path.of("").toAbsolutePath();
        Path repo = Files.isRegularFile(cwd.resolve("services/ai-service/.venv/Scripts/python.exe"))
                ? cwd
                : cwd.getParent().getParent();
        Path python = repo.resolve("services/ai-service/.venv/Scripts/python.exe");
        Path script = repo.resolve("services/ai-service/hl7_hospital_live.py");
        assertThat(python).isRegularFile();
        Path ledger = Files.createTempDirectory("hl7-002-agent").toAbsolutePath();
        ProcessBuilder builder = new ProcessBuilder(python.toString(), script.toString());
        builder.directory(repo.resolve("services/ai-service").toFile());
        builder.environment().put("HL7_FEDERATION_URL", "http://127.0.0.1:" + exchangePort);
        builder.environment().put("HL7_FEDERATION_TOKEN", FED_TOKEN);
        builder.environment().put("HL7_LEDGER_DIR", ledger.toString());
        builder.environment().put("HL7_REVIEW_DB", ledger.resolve("review.sqlite3").toString());
        builder.environment().put("HL7_LIS_OBSERVATION_ID", lisResultId);
        builder.environment().put("HL7_HIS_OBSERVATION_ID", HIS_OBSERVATION);
        builder.redirectErrorStream(true);
        Process process = builder.start();
        ByteArrayOutputStream captured = new ByteArrayOutputStream();
        process.getInputStream().transferTo(captured);
        assertThat(process.waitFor(120, TimeUnit.SECONDS)).isTrue();
        String output = captured.toString(StandardCharsets.UTF_8).replace(FED_TOKEN, "[token]");
        assertThat(process.exitValue()).as(output).isZero();
        String report = output.lines().filter(line -> line.startsWith("{")).reduce((first, second) -> second).orElse("");
        return json.readTree(report);
    }

    private static Map<String, String> outcomes(JsonNode federation) {
        Map<String, String> outcomes = new HashMap<>();
        federation.path("sources").forEach(source -> outcomes.put(
                source.path("sourceKey").asText(), source.path("outcome").asText()));
        return outcomes;
    }

    private static JsonNode entry(JsonNode federation, String source, String type, String id) {
        List<JsonNode> matches = new ArrayList<>();
        federation.path("entries").forEach(entry -> {
            JsonNode resource = entry.path("resource");
            if (source.equals(entry.path("sourceKey").asText())
                    && type.equals(resource.path("resourceType").asText())
                    && id.equals(resource.path("id").asText())) {
                matches.add(resource);
            }
        });
        assertThat(matches).hasSize(1);
        return matches.get(0);
    }

    private static boolean cited(JsonNode agent, String source, String id) {
        for (JsonNode item : agent.path("cited")) {
            if (source.equals(item.get(0).asText())
                    && "Observation".equals(item.get(1).asText())
                    && id.equals(item.get(2).asText())) {
                return true;
            }
        }
        return false;
    }

    private static void startLaboratory() throws Exception {
        if (lis != null) {
            return;
        }
        try (ServerSocket reserved = new ServerSocket()) {
            reserved.setReuseAddress(true);
            reserved.bind(new InetSocketAddress("127.0.0.1", 0));
            exchangePort = reserved.getLocalPort();
        }
        storePath = Path.of(System.getProperty("java.io.tmpdir"), "exchange-hl7-hospital-" + System.nanoTime() + ".sqlite").toString();
        auditPath = Path.of(System.getProperty("java.io.tmpdir"), "federation-hl7-hospital-" + System.nanoTime() + ".sqlite").toString();
        postgres = new PostgreSQLContainer<>("postgres:16-alpine");
        postgres.start();
        SpringApplication lisApplication = new SpringApplication(MiniLisApplication.class);
        HashMap<String, Object> lisProperties = new HashMap<>();
        lisProperties.put("server.port", "0");
        lisProperties.put("server.address", "127.0.0.1");
        lisProperties.put("spring.main.banner-mode", "off");
        lisProperties.put("spring.datasource.url", postgres.getJdbcUrl());
        lisProperties.put("spring.datasource.username", postgres.getUsername());
        lisProperties.put("spring.datasource.password", postgres.getPassword());
        lisProperties.put("mini-lis.service-token", LIS_TOKEN);
        lisProperties.put("mini-lis.hl7.enabled", "true");
        lisProperties.put("mini-lis.hl7.port", "0");
        lisProperties.put("mini-lis.hl7.shared-secret", SECRET);
        lisProperties.put("mini-lis.hl7.bind-address", "127.0.0.1");
        lisApplication.setDefaultProperties(lisProperties);
        lis = lisApplication.run("--server.port=0", "--server.address=127.0.0.1");
        lisUrl = "http://127.0.0.1:" + lis.getEnvironment().getProperty("local.server.port");
        lisHl7Port = lis.getBean(Hl7Server.class).port();

        Path database = Path.of(System.getProperty("java.io.tmpdir"), "mini-his-hl7-hospital-" + System.nanoTime() + ".sqlite");
        SpringApplication hisApplication = new SpringApplication(MiniHisSimulatorApplication.class);
        hisApplication.setDefaultProperties(Map.of(
                "server.port", "0",
                "server.address", "127.0.0.1",
                "spring.main.banner-mode", "off",
                "mini-his.sqlite-path", database.toString(),
                "spring.flyway.enabled", "false",
                "mini-his.organization-id", "org-mini-his",
                "mini-his.exchange.base-url", "http://127.0.0.1:" + exchangePort,
                "mini-his.exchange.service-token", HIS_TOKEN));
        his = hisApplication.run("--server.port=0", "--server.address=127.0.0.1");
        hisUrl = "http://127.0.0.1:" + his.getEnvironment().getProperty("local.server.port");
    }

    private JsonNode send(String method, String url, String body, String token) throws Exception {
        HttpRequest.Builder request = HttpRequest.newBuilder(URI.create(url)).timeout(Duration.ofSeconds(20));
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

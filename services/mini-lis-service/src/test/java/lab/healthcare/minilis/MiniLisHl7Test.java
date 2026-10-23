package lab.healthcare.minilis;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

import java.net.ServerSocket;
import java.net.Socket;
import java.time.Duration;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.concurrent.atomic.AtomicReference;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@Testcontainers
@SpringBootTest
@AutoConfigureMockMvc
class MiniLisHl7Test {

    private static final String TOKEN = "hl7-lis-token";
    private static final String SECRET = "hl7-lis-secret";

    @Container
    static final PostgreSQLContainer<?> POSTGRES = new PostgreSQLContainer<>("postgres:16-alpine");

    @DynamicPropertySource
    static void database(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", POSTGRES::getJdbcUrl);
        registry.add("spring.datasource.username", POSTGRES::getUsername);
        registry.add("spring.datasource.password", POSTGRES::getPassword);
        registry.add("mini-lis.service-token", () -> TOKEN);
        registry.add("mini-lis.hl7.enabled", () -> "true");
        registry.add("mini-lis.hl7.port", () -> "0");
        registry.add("mini-lis.hl7.shared-secret", () -> SECRET);
        registry.add("mini-lis.hl7.allowed-organizations", () -> "org-mini-his");
        registry.add("mini-lis.hl7.outbound-port", () -> "0");
    }

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private Hl7Server server;

    private final Hl7Messages messages = new Hl7Messages();

    @Test
    void omlIsAcceptedOnceAndAReplayDoesNotCreateAnotherOrder() throws Exception {
        String first = send(order("MSG-ORDER-001", "MHS-LAB-HL7-1", SECRET, "org-mini-his"));
        assertThat(messageType(first)).isEqualTo("ORL");
        assertThat(ackCode(first)).isEqualTo("AA");
        assertThat(ackDetail(first)).isEmpty();
        assertThat(field(first, "/RESPONSE/PATIENT/ORDER/ORC-1")).isEqualTo("OK");
        String orderId = field(first, "/RESPONSE/PATIENT/ORDER/ORC-3-1");
        String patientId = field(first, "/RESPONSE/PATIENT/PID-3-1");
        assertThat(orderId).startsWith("MLS-ORD-");
        assertThat(patientId).startsWith("MLS-PAT-");
        String replay = send(order("MSG-ORDER-001", "MHS-LAB-HL7-1", SECRET, "org-mini-his"));
        assertThat(field(replay, "/RESPONSE/PATIENT/ORDER/ORC-3-1")).isEqualTo(orderId);
        assertThat(field(replay, "/RESPONSE/PATIENT/PID-3-1")).isEqualTo(patientId);
        String repeatedPlacer = send(order("MSG-ORDER-002", "MHS-LAB-HL7-1", SECRET, "org-mini-his"));
        assertThat(ackDetail(repeatedPlacer)).isEqualTo("duplicate");
        assertThat(field(repeatedPlacer, "/RESPONSE/PATIENT/ORDER/ORC-3-1")).isEqualTo(orderId);
        mockMvc.perform(get("/orders")
                        .param("requestingOrganizationId", "org-mini-his")
                        .param("externalRequestId", "MHS-LAB-HL7-1")
                        .header("X-Service-Token", TOKEN))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.orderId").value(orderId));
    }

    @Test
    void aWrongSecretOrOrganizationDoesNotCreateAnOrder() throws Exception {
        String unauthorized = send(order("MSG-BAD-SECRET", "MHS-LAB-HL7-2", "other-secret", "org-mini-his"));
        assertThat(ackCode(unauthorized)).isEqualTo("AR");
        assertThat(ackDetail(unauthorized)).isEqualTo("unauthorized");
        String forbidden = send(order("MSG-BAD-ORG", "MHS-LAB-HL7-3", SECRET, "org-clinic-b"));
        assertThat(ackCode(forbidden)).isEqualTo("AE");
        assertThat(ackDetail(forbidden)).isEqualTo("organization_forbidden");
        String invalid = send("this is not hl7");
        assertThat(ackCode(invalid)).isEqualTo("AR");
        String blankSecret = send(order("MSG-BLANK-SECRET", "MHS-LAB-HL7-4", "", "org-mini-his"));
        assertThat(ackCode(blankSecret)).isEqualTo("AR");
        assertThat(ackDetail(blankSecret)).isEqualTo("unauthorized");
        String wrongSender = send(order("MSG-WRONG-SENDER", "MHS-LAB-HL7-5", SECRET, "org-mini-his", "OTHER-APP"));
        assertThat(ackCode(wrongSender)).isEqualTo("AR");
        assertThat(ackDetail(wrongSender)).isEqualTo("unauthorized");
        mockMvc.perform(get("/orders")
                        .param("requestingOrganizationId", "org-mini-his")
                        .param("externalRequestId", "MHS-LAB-HL7-2")
                        .header("X-Service-Token", TOKEN))
                .andExpect(status().isNotFound());
        mockMvc.perform(get("/orders")
                        .param("requestingOrganizationId", "org-mini-his")
                        .param("externalRequestId", "MHS-LAB-HL7-4")
                        .header("X-Service-Token", TOKEN))
                .andExpect(status().isNotFound());
        mockMvc.perform(get("/orders")
                        .param("requestingOrganizationId", "org-mini-his")
                        .param("externalRequestId", "MHS-LAB-HL7-5")
                        .header("X-Service-Token", TOKEN))
                .andExpect(status().isNotFound());
    }

    @Test
    void aCommittedResultIsPublishedAsOruAndALostAckCanBeRetried() throws Exception {
        String accepted = send(order("MSG-ORDER-010", "MHS-LAB-HL7-10", SECRET, "org-mini-his"));
        String orderId = field(accepted, "/RESPONSE/PATIENT/ORDER/ORC-3-1");
        AtomicReference<String> captured = new AtomicReference<>();
        try (ServerSocket peer = MllpExchange.listen("127.0.0.1", 0)) {
            Thread listener = new Thread(() -> {
                try (Socket socket = peer.accept()) {
                    captured.set(MllpExchange.read(socket.getInputStream()));
                    MllpExchange.write(socket.getOutputStream(), messages.ack("FHIR-EXCHANGE", "fhir-integration-service", "R01", "AA", "IGNORED", "order=" + orderId));
                } catch (Exception ex) {
                    captured.set("failed");
                }
            });
            listener.start();
            mockMvc.perform(put("/hl7/result-peer")
                            .header("X-Service-Token", TOKEN)
                            .contentType(MediaType.APPLICATION_JSON)
                            .content("{\"host\":\"127.0.0.1\",\"port\":" + peer.getLocalPort() + "}"))
                    .andExpect(status().isOk());
            mockMvc.perform(post("/orders/" + orderId + "/results")
                            .header("X-Service-Token", TOKEN)
                            .contentType(MediaType.APPLICATION_JSON)
                            .content("""
                                    {"externalResultId":"EXT-RES-HL7","testCode":"GLU","value":"141","unit":"mmol/L","referenceRange":"70-110","resultedAt":"2026-03-01T12:00:00Z","status":"FINAL"}
                                    """))
                    .andExpect(status().isCreated());
            listener.join(5000);
        }
        assertThat(captured.get()).contains("ORU^R01").contains("141").contains("mmol/L").doesNotContain("loinc").doesNotContain("ucum");
        Hl7Messages.ParsedMessage parsed = messages.parse(captured.get());
        assertThat(Hl7Messages.value(parsed.terser(), "/PATIENT_RESULT/ORDER_OBSERVATION/OBSERVATION/OBX-5")).isEqualTo("141");
        assertThat(Hl7Messages.value(parsed.terser(), "/PATIENT_RESULT/ORDER_OBSERVATION/OBSERVATION/OBX-6-1")).isEqualTo("mmol/L");
        assertThat(Hl7Messages.value(parsed.terser(), "/PATIENT_RESULT/ORDER_OBSERVATION/OBSERVATION/OBX-6-3")).isEmpty();
        assertThat(Hl7Messages.value(parsed.terser(), "/PATIENT_RESULT/ORDER_OBSERVATION/ORC-3-1")).isEqualTo(orderId);
        assertThat(Hl7Messages.value(parsed.terser(), "/PATIENT_RESULT/ORDER_OBSERVATION/ORC-5")).isEqualTo("IP");
        assertThat(Hl7Messages.value(parsed.terser(), "/PATIENT_RESULT/ORDER_OBSERVATION/ORC-21-10")).isEqualTo("org-mini-his");
        assertThat(Hl7Messages.value(parsed.terser(), "/PATIENT_RESULT/ORDER_OBSERVATION/ORC-21-1")).isEmpty();
        assertThat(Hl7Messages.value(parsed.terser(), "/PATIENT_RESULT/ORDER_OBSERVATION/OBSERVATION/OBX-4")).isEqualTo("EXT-RES-HL7");
        assertThat(Hl7Messages.value(parsed.terser(), "/PATIENT_RESULT/ORDER_OBSERVATION/OBSERVATION/OBX-11")).isEqualTo("F");
    }

    @Test
    void aFailedPublicationKeepsTheResultAndARetryReusesTheControlId() throws Exception {
        String accepted = send(order("MSG-ORDER-020", "MHS-LAB-HL7-20", SECRET, "org-mini-his"));
        String orderId = field(accepted, "/RESPONSE/PATIENT/ORDER/ORC-3-1");
        int deadPort;
        try (java.net.ServerSocket closed = new java.net.ServerSocket()) {
            closed.bind(new java.net.InetSocketAddress("127.0.0.1", 0));
            deadPort = closed.getLocalPort();
        }
        mockMvc.perform(put("/hl7/result-peer")
                        .header("X-Service-Token", TOKEN)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"host\":\"127.0.0.1\",\"port\":" + deadPort + "}"))
                .andExpect(status().isOk());
        String created = mockMvc.perform(post("/orders/" + orderId + "/results")
                        .header("X-Service-Token", TOKEN)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"externalResultId":"EXT-RES-RETRY","testCode":"GLU","value":"141","unit":"mmol/L","referenceRange":"70-110","resultedAt":"2026-03-01T12:00:00Z","status":"FINAL"}
                                """))
                .andExpect(status().isCreated())
                .andReturn().getResponse().getContentAsString();
        String resultId = new com.fasterxml.jackson.databind.ObjectMapper().readTree(created).path("resultId").asText();
        mockMvc.perform(get("/orders/" + orderId + "/results").header("X-Service-Token", TOKEN))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0].status").value("FINAL"))
                .andExpect(jsonPath("$[0].value").value("141"));
        mockMvc.perform(post("/hl7/results/" + resultId + "/publication").header("X-Service-Token", TOKEN))
                .andExpect(status().isServiceUnavailable())
                .andExpect(jsonPath("$.error").value("destination_unavailable"));
        AtomicReference<String> firstMessage = new AtomicReference<>();
        AtomicReference<String> secondMessage = new AtomicReference<>();
        try (java.net.ServerSocket peer = MllpExchange.listen("127.0.0.1", 0)) {
            mockMvc.perform(put("/hl7/result-peer")
                            .header("X-Service-Token", TOKEN)
                            .contentType(MediaType.APPLICATION_JSON)
                            .content("{\"host\":\"127.0.0.1\",\"port\":" + peer.getLocalPort() + "}"))
                    .andExpect(status().isOk());
            Thread first = new Thread(() -> capture(peer, firstMessage, resultId));
            first.start();
            mockMvc.perform(post("/hl7/results/" + resultId + "/publication").header("X-Service-Token", TOKEN))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.ack").value("AA"));
            first.join(5000);
            Thread second = new Thread(() -> capture(peer, secondMessage, resultId));
            second.start();
            mockMvc.perform(post("/hl7/results/" + resultId + "/publication").header("X-Service-Token", TOKEN))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.ack").value("AA"));
            second.join(5000);
        }
        assertThat(field(firstMessage.get(), "/MSH-10")).isEqualTo(resultId);
        assertThat(field(secondMessage.get(), "/MSH-10")).isEqualTo(resultId);
        mockMvc.perform(get("/results/" + resultId).header("X-Service-Token", TOKEN))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("FINAL"))
                .andExpect(jsonPath("$.value").value("141"));
    }

    @Test
    void theResultPeerRejectsANonLoopbackAddress() throws Exception {
        mockMvc.perform(put("/hl7/result-peer")
                        .header("X-Service-Token", TOKEN)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"host\":\"8.8.8.8\",\"port\":2576}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error").value("invalid_request"));
    }

    private String send(String er7) throws Exception {
        return MllpExchange.transact("127.0.0.1", server.port(), er7, Duration.ofSeconds(2), Duration.ofSeconds(5));
    }

    private void capture(java.net.ServerSocket peer, AtomicReference<String> target, String resultId) {
        try (java.net.Socket socket = peer.accept()) {
            target.set(MllpExchange.read(socket.getInputStream()));
            MllpExchange.write(socket.getOutputStream(), messages.ack(
                    "FHIR-EXCHANGE", "fhir-integration-service", "R01", "AA", resultId, ""));
        } catch (Exception ex) {
            target.set("failed");
        }
    }

    private String order(String controlId, String placer, String secret, String organization) {
        return order(controlId, placer, secret, organization, "FHIR-EXCHANGE");
    }

    private String order(String controlId, String placer, String secret, String organization, String sendingApplication) {
        return messages.oml(new Hl7Messages.OmlPayload(
                sendingApplication,
                "fhir-integration-service",
                "MINI-LIS",
                "org-mini-lis",
                secret,
                controlId,
                organization,
                "MHS-PAT-001",
                "Quispe",
                "Ana",
                LocalDate.parse("1984-03-12"),
                "female",
                placer,
                "GLU",
                "Glucose",
                "https://lab.local/mini-his/test",
                OffsetDateTime.parse("2026-03-01T10:00:00Z")));
    }

    private String ackCode(String er7) {
        return Hl7Messages.value(messages.parse(er7).terser(), "/MSA-1");
    }

    private String ackDetail(String er7) {
        return Hl7Messages.value(messages.parse(er7).terser(), "/MSA-3");
    }

    private String messageType(String er7) {
        return messages.parse(er7).type();
    }

    private String field(String er7, String path) {
        return Hl7Messages.value(messages.parse(er7).terser(), path);
    }

}

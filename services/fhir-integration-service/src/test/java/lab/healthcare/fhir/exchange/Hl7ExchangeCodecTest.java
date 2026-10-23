package lab.healthcare.fhir.exchange;

import lab.healthcare.fhir.clinicalread.minilis.MiniLisFhirMapping;
import lab.healthcare.minilis.Hl7Messages;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.junit.jupiter.api.Test;

import java.net.ServerSocket;
import java.net.Socket;
import java.time.Duration;
import java.time.LocalDate;
import java.time.OffsetDateTime;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class Hl7ExchangeCodecTest {

    private final ObjectMapper json = new ObjectMapper();
    private final Hl7ExchangeCodec codec = new Hl7ExchangeCodec();
    private final Hl7Messages lis = new Hl7Messages();

    @Test
    void anOmlUsesTheProfileAndCarriesNoLoinc() {
        ExchangeProperties.Hl7 peer = new ExchangeProperties.Hl7();
        String er7 = codec.oml(peer, "MSG-UNIT-1", "secret", command(), patient());
        Hl7Messages.ParsedMessage parsed = lis.parse(er7);
        assertThat(parsed.type()).isEqualTo("OML");
        assertThat(parsed.event()).isEqualTo("O21");
        assertThat(Hl7Messages.value(parsed.terser(), "/MSH-12")).isEqualTo("2.5.1");
        assertThat(Hl7Messages.value(parsed.terser(), "/ORDER/ORC-1")).isEqualTo("NW");
        assertThat(Hl7Messages.value(parsed.terser(), "/ORDER/ORC-2-1")).isEqualTo("MHS-LAB-001");
        assertThat(Hl7Messages.value(parsed.terser(), "/ORDER/ORC-21-10")).isEqualTo("org-mini-his");
        assertThat(Hl7Messages.value(parsed.terser(), "/ORDER/ORC-21-1")).isEmpty();
        assertThat(Hl7Messages.value(parsed.terser(), "/PATIENT/PID-3-1")).isEqualTo("MHS-PAT-001");
        assertThat(Hl7Messages.value(parsed.terser(), "/PATIENT/PID-3-4")).isEqualTo("org-mini-his");
        assertThat(Hl7Messages.value(parsed.terser(), "/ORDER/OBSERVATION_REQUEST/OBR-4-1")).isEqualTo("GLU");
        assertThat(Hl7Messages.value(parsed.terser(), "/ORDER/OBSERVATION_REQUEST/OBR-4-2")).isEqualTo("Glucose & load");
        assertThat(er7).contains("\\T\\");
        assertThat(er7.toLowerCase()).doesNotContain("loinc").doesNotContain("ucum");
    }

    @Test
    void anOruAndTheRestPayloadNormalizeToTheSameObservation() {
        String oru = lis.oru(new Hl7Messages.OruPayload(
                "MINI-LIS",
                "org-mini-lis",
                "FHIR-EXCHANGE",
                "fhir-integration-service",
                "secret",
                "MLS-RES-1",
                "org-mini-his",
                "MHS-PAT-001",
                "Quispe",
                "Ana",
                LocalDate.parse("1984-03-12"),
                "female",
                "MHS-LAB-001",
                "MLS-ORD-1",
                "IN_PROGRESS",
                "GLU",
                "Glucose",
                OffsetDateTime.parse("2026-03-01T10:00:00Z"),
                "EXT-RES-1",
                "141",
                "mmol/L",
                "70-110",
                "FINAL",
                OffsetDateTime.parse("2026-03-01T12:00:00Z")));
        Hl7ExchangeCodec.Oru parsed = codec.oru(oru);
        assertThat(parsed.forbiddenCodeSystem()).isFalse();
        ObjectNode fromHl7 = result(parsed);
        ObjectNode fromRest = json.createObjectNode();
        fromRest.put("resultId", "MLS-RES-1");
        fromRest.put("orderId", "MLS-ORD-1");
        fromRest.put("patientId", "MLS-PAT-1");
        fromRest.put("externalResultId", "EXT-RES-1");
        fromRest.put("testCode", "GLU");
        fromRest.put("value", "141");
        fromRest.put("unit", "mmol/L");
        fromRest.put("referenceRange", "70-110");
        fromRest.put("resultedAt", "2026-03-01T12:00:00Z");
        fromRest.put("status", "FINAL");
        MiniLisFhirMapping mapping = new MiniLisFhirMapping(json);
        JsonNode hl7Observation = mapping.observation(fromHl7);
        JsonNode restObservation = mapping.observation(fromRest);
        assertThat(hl7Observation.path("valueQuantity").path("value").asText()).isEqualTo("141");
        assertThat(hl7Observation.path("valueQuantity").path("unit").asText()).isEqualTo("mmol/L");
        assertThat(hl7Observation.path("valueQuantity").has("system")).isFalse();
        assertThat(hl7Observation.path("code").path("coding").get(0).path("code").asText())
                .isEqualTo(restObservation.path("code").path("coding").get(0).path("code").asText());
        assertThat(hl7Observation.path("status").asText()).isEqualTo(restObservation.path("status").asText()).isEqualTo("final");
        assertThat(hl7Observation.path("basedOn").get(0).path("reference").asText())
                .isEqualTo(restObservation.path("basedOn").get(0).path("reference").asText())
                .isEqualTo("ServiceRequest/MLS-ORD-1");
        assertThat(hl7Observation.path("subject").path("reference").asText())
                .isEqualTo(restObservation.path("subject").path("reference").asText())
                .isEqualTo("Patient/MLS-PAT-1");
        assertThat(hl7Observation.path("effectiveDateTime").asText()).isEqualTo(restObservation.path("effectiveDateTime").asText());
        assertThat(hl7Observation.path("referenceRange").get(0).path("text").asText()).isEqualTo("70-110");
        assertThat(hl7Observation.path("identifier").get(0).path("value").asText())
                .isEqualTo(restObservation.path("identifier").get(0).path("value").asText())
                .isEqualTo("EXT-RES-1");
        assertThat(hl7Observation.path("meta").path("source").asText()).isEqualTo(restObservation.path("meta").path("source").asText());
        assertThat(parsed.externalPatientId()).isEqualTo("MHS-PAT-001");
        assertThat(parsed.organizationId()).isEqualTo("org-mini-his");
        assertThat(parsed.orderingOrganizationId()).isEqualTo("org-mini-his");
        assertThat(parsed.orderStatus()).isEqualTo("IP");
        assertThat(hl7Observation.toString()).doesNotContain("loinc").doesNotContain("ucum");
        JsonNode hl7Report = mapping.diagnosticReport(order(), json.createArrayNode().add(fromHl7));
        JsonNode restReport = mapping.diagnosticReport(order(), json.createArrayNode().add(fromRest));
        assertThat(hl7Report.path("status").asText()).isEqualTo(restReport.path("status").asText()).isEqualTo("partial");
        assertThat(hl7Report.path("subject").path("reference").asText()).isEqualTo("Patient/MLS-PAT-1");
        assertThat(hl7Report.path("basedOn").get(0).path("reference").asText()).isEqualTo("ServiceRequest/MLS-ORD-1");
        assertThat(hl7Report.path("code").path("coding").get(0).path("code").asText()).isEqualTo("GLU");
        assertThat(hl7Report.path("result").get(0).path("reference").asText()).isEqualTo("Observation/MLS-RES-1");
        JsonNode serviceRequest = mapping.serviceRequest(order());
        assertThat(serviceRequest.path("requester").path("identifier").path("value").asText()).isEqualTo("org-mini-his");
        assertThat(serviceRequest.path("authoredOn").asText()).contains("2026-03-01T10:00:00");
    }

    @Test
    void aNegativeAckAndATimeoutAreDistinct() throws Exception {
        String ack = codec.ackMessage(new ExchangeProperties.Hl7(), "O21", "AE", "MSG-ERR", "invalid_request");
        assertThat(codec.ack(ack).code()).isEqualTo("AE");
        assertThat(codec.ack(ack).detail()).isEqualTo("invalid_request");
        try (ServerSocket server = MllpSession.listen(0)) {
            Thread held = new Thread(() -> {
                try (Socket socket = server.accept()) {
                    Thread.sleep(2000);
                } catch (Exception ignored) {
                    // The client is expected to time out.
                }
            });
            held.start();
            assertThatThrownBy(() -> MllpSession.transact(
                    "127.0.0.1", server.getLocalPort(), "MSH|^~\\&|A|B|||000000||ACK^O21|1|P|2.5.1\r",
                    Duration.ofMillis(300), Duration.ofMillis(300)))
                    .isInstanceOf(java.io.IOException.class);
        }
    }

    private static DestinationCommand command() {
        return new DestinationCommand(
                "MHS-PAT-001",
                "org-mini-his",
                "MHS-LAB-001",
                "GLU",
                "Glucose & load",
                OffsetDateTime.parse("2026-03-01T10:00:00Z"),
                "org-mini-lis",
                "https://lab.local/mini-his/test");
    }

    private static PatientIdentity patient() {
        return new PatientIdentity(
                "https://lab.local/mini-his/patient",
                "MHS-PAT-001",
                "Quispe",
                "Ana",
                LocalDate.parse("1984-03-12"),
                "female");
    }

    private ObjectNode result(Hl7ExchangeCodec.Oru parsed) {
        ObjectNode body = json.createObjectNode();
        body.put("resultId", parsed.controlId());
        body.put("orderId", parsed.fillerOrderId());
        body.put("patientId", "MLS-PAT-1");
        body.put("externalResultId", parsed.externalResultId());
        body.put("testCode", parsed.testCode());
        body.put("value", parsed.value());
        body.put("unit", parsed.unit());
        body.put("referenceRange", parsed.referenceRange());
        body.put("resultedAt", Hl7ExchangeCodec.parseTime(parsed.resultedAt()).toString());
        body.put("status", "FINAL");
        return body;
    }

    private ObjectNode order() {
        ObjectNode body = json.createObjectNode();
        body.put("orderId", "MLS-ORD-1");
        body.put("patientId", "MLS-PAT-1");
        body.put("requestingOrganizationId", "org-mini-his");
        body.put("externalRequestId", "MHS-LAB-001");
        body.put("testCode", "GLU");
        body.put("testDescription", "Glucose");
        body.put("requestedAt", "2026-03-01T10:00:00Z");
        body.put("status", "IN_PROGRESS");
        return body;
    }
}

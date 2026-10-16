package lab.healthcare.fhir.clinicalread.minihis;

import lab.healthcare.fhir.clinicalread.ClinicalReadException;
import lab.healthcare.fhir.clinicalread.ClinicalReadService;
import lab.healthcare.fhir.routing.RoutingService;
import lab.healthcare.fhir.server.FhirServersProperties;

import ca.uhn.fhir.context.BaseRuntimeChildDefinition;
import ca.uhn.fhir.context.FhirContext;
import ca.uhn.fhir.context.RuntimeResourceDefinition;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.sun.net.httpserver.HttpServer;
import org.hl7.fhir.instance.model.api.IBaseResource;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.atomic.AtomicInteger;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.verifyNoInteractions;

@ExtendWith(MockitoExtension.class)
class MiniHisConnectorTest {

    private final ObjectMapper json = new ObjectMapper();

    @Mock
    private RoutingService routing;

    @Test
    void mapsPatientConsultationAndResultWithoutInventingMissingFields() {
        MiniHisNormalizer normalizer = new MiniHisNormalizer(json);
        ObjectNode patient = normalizer.patient(json.createObjectNode()
                .put("patientId", "MHS-PAT-001")
                .put("familyName", "Quispe")
                .put("givenName", "Ana")
                .put("birthDate", "1984-03-12")
                .put("administrativeSex", "female"));
        ObjectNode encounter = normalizer.encounter(json.createObjectNode()
                .put("consultationId", "MHS-CON-001")
                .put("patientId", "MHS-PAT-001")
                .put("occurredAt", "2026-09-01T15:00:00Z")
                .put("reason", "Control de laboratorio sintetico")
                .put("clinicianName", "Dra. Luz Demo")
                .put("status", "in_progress")
                .put("careClass", "ambulatory"));
        ObjectNode observation = normalizer.observation(json.createObjectNode()
                .put("resultId", "MHS-RES-001")
                .put("consultationId", "MHS-CON-001")
                .put("patientId", "MHS-PAT-001")
                .put("resultType", "laboratory")
                .put("displayName", "Hemoglobina")
                .put("valueText", "13.4")
                .put("unit", "g/dL")
                .put("observedAt", "2026-09-01T15:10:00Z")
                .put("status", "final"));

        assertThat(patient.path("id").asText()).isEqualTo("MHS-PAT-001");
        assertThat(patient.path("meta").path("source").asText()).isEqualTo(MiniHisNormalizer.SOURCE);
        assertThat(patient.path("identifier").get(0).path("system").asText()).isEqualTo(MiniHisNormalizer.PATIENT_SYSTEM);
        assertThat(patient.path("identifier").get(0).path("value").asText()).isEqualTo("MHS-PAT-001");
        assertThat(patient.path("gender").asText()).isEqualTo("female");
        assertThat(patient.path("birthDate").asText()).isEqualTo("1984-03-12");
        assertThat(encounter.path("status").asText()).isEqualTo("in-progress");
        assertThat(encounter.path("class").path("system").asText()).isEqualTo(MiniHisNormalizer.ENCOUNTER_CLASS_SYSTEM);
        assertThat(encounter.path("class").path("code").asText()).isEqualTo("AMB");
        assertThat(encounter.path("class").path("display").asText()).isEqualTo("ambulatory");
        assertThat(encounter.path("subject").path("reference").asText()).isEqualTo("Patient/MHS-PAT-001");
        assertThat(encounter.path("period").path("start").asText()).isEqualTo("2026-09-01T15:00:00Z");
        assertThat(observation.path("status").asText()).isEqualTo("final");
        assertThat(observation.path("subject").path("reference").asText()).isEqualTo("Patient/MHS-PAT-001");
        assertThat(observation.path("encounter").path("reference").asText()).isEqualTo("Encounter/MHS-CON-001");
        assertThat(observation.path("category").get(0).path("coding").get(0).path("code").asText()).isEqualTo("laboratory");
        assertThat(observation.path("valueQuantity").path("value").decimalValue()).isEqualByComparingTo("13.4");
        assertThat(observation.path("valueQuantity").path("unit").asText()).isEqualTo("g/dL");
        assertThat(observation.path("effectiveDateTime").asText()).isEqualTo("2026-09-01T15:10:00Z");
        assertRequiredR4Elements(patient, encounter, observation);
    }

    @Test
    void missingOrInconsistentSourceDataIsAnExplicitError() {
        MiniHisNormalizer normalizer = new MiniHisNormalizer(json);
        assertThatThrownBy(() -> normalizer.patient(json.createObjectNode()
                        .put("patientId", "MHS-PAT-001")
                        .put("givenName", "Ana")
                        .put("administrativeSex", "female")))
                .isInstanceOf(ClinicalReadException.class)
                .extracting(ex -> ((ClinicalReadException) ex).code())
                .isEqualTo("invalid_source");
        assertThatThrownBy(() -> normalizer.encounter(json.createObjectNode()
                        .put("consultationId", "MHS-CON-001")
                        .put("patientId", "MHS-PAT-001")
                        .put("occurredAt", "2026-09-01T15:00:00Z")
                        .put("status", "planned")
                        .put("careClass", "ambulatory")))
                .isInstanceOf(ClinicalReadException.class)
                .extracting(ex -> ((ClinicalReadException) ex).code())
                .isEqualTo("invalid_source");
        assertThatThrownBy(() -> normalizer.observation(json.createObjectNode()
                        .put("resultId", "MHS-RES-009")
                        .put("consultationId", "MHS-CON-001")
                        .put("patientId", "MHS-PAT-001")
                        .put("resultType", "laboratory")
                        .put("displayName", "Nota")
                        .put("valueText", "positivo")
                        .put("unit", "g/dL")
                        .put("status", "final")))
                .isInstanceOf(ClinicalReadException.class)
                .extracting(ex -> ((ClinicalReadException) ex).code())
                .isEqualTo("invalid_source");
        assertThatThrownBy(() -> normalizer.encounter(json.createObjectNode()
                        .put("consultationId", "MHS-CON-001")
                        .put("patientId", "MHS-PAT-001")
                        .put("occurredAt", "2026-09-01T15:00:00Z")
                        .put("status", "completed")
                        .put("careClass", "inpatient")))
                .isInstanceOf(ClinicalReadException.class)
                .extracting(ex -> ((ClinicalReadException) ex).code())
                .isEqualTo("invalid_source");
        assertThatThrownBy(() -> normalizer.observation(json.createObjectNode()
                        .put("resultId", "MHS-RES-009")
                        .put("consultationId", "MHS-CON-001")
                        .put("patientId", "MHS-PAT-001")
                        .put("resultType", "laboratory")
                        .put("displayName", "Hemoglobina")
                        .put("status", "preliminary")))
                .isInstanceOf(ClinicalReadException.class)
                .extracting(ex -> ((ClinicalReadException) ex).code())
                .isEqualTo("invalid_source");
    }

    @Test
    void readsSupportedResourcesAndRejectsAppointmentWithoutCallingHapi() throws IOException {
        AtomicInteger requests = new AtomicInteger();
        List<String> paths = new CopyOnWriteArrayList<>();
        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/", exchange -> {
            requests.incrementAndGet();
            String path = exchange.getRequestURI().getPath();
            paths.add(path);
            if (!"GET".equals(exchange.getRequestMethod())) {
                exchange.sendResponseHeaders(405, -1);
                return;
            }
            byte[] body = switch (path) {
                case "/patients/MHS-PAT-001" -> patientJson().getBytes(StandardCharsets.UTF_8);
                case "/patients/MHS-PAT-001/consultations" -> consultationsJson().getBytes(StandardCharsets.UTF_8);
                case "/consultations/MHS-CON-001" -> consultationJson().getBytes(StandardCharsets.UTF_8);
                case "/results/MHS-RES-001" -> resultJson().getBytes(StandardCharsets.UTF_8);
                default -> null;
            };
            if (body == null) {
                byte[] missing = "{\"error\":\"not_found\"}".getBytes(StandardCharsets.UTF_8);
                exchange.getResponseHeaders().set("Content-Type", "application/json");
                exchange.sendResponseHeaders(404, missing.length);
                try (OutputStream output = exchange.getResponseBody()) {
                    output.write(missing);
                }
                return;
            }
            exchange.getResponseHeaders().set("Content-Type", "application/json");
            exchange.sendResponseHeaders(200, body.length);
            try (OutputStream output = exchange.getResponseBody()) {
                output.write(body);
            }
        });
        server.start();
        try {
            MiniHisClinicalSource source = source("http://127.0.0.1:" + server.getAddress().getPort());
            JsonNode patient = source.readPatient("MHS-PAT-001");
            JsonNode patients = source.searchPatients(MiniHisNormalizer.PATIENT_SYSTEM, "MHS-PAT-001");
            JsonNode encounters = source.searchEncounters("MHS-PAT-001", "finished");
            JsonNode encounter = source.readEncounter("MHS-CON-001");
            int beforeObservation = paths.size();
            JsonNode observation = source.readObservation("MHS-RES-001");
            int beforeUnsupported = requests.get();

            assertThat(patient.path("destination").asText()).isEqualTo("mini-his");
            assertThat(patient.path("resource").path("id").asText()).isEqualTo("MHS-PAT-001");
            assertThat(patients.path("collectionStatus").asText()).isEqualTo("complete");
            assertThat(patients.path("resources").get(0).path("id").asText()).isEqualTo("MHS-PAT-001");
            assertThat(encounters.path("resources").get(0).path("id").asText()).isEqualTo("MHS-CON-001");
            assertThat(encounters.path("resources").get(0).path("status").asText()).isEqualTo("finished");
            assertThat(encounter.path("resource").path("class").path("code").asText()).isEqualTo("AMB");
            assertThat(encounter.path("resource").path("subject").path("reference").asText())
                    .isEqualTo("Patient/MHS-PAT-001");
            assertThat(paths.subList(beforeObservation, paths.size())).containsExactly("/results/MHS-RES-001");
            assertThat(observation.path("resource").path("status").asText()).isEqualTo("final");
            assertThat(observation.path("resource").path("encounter").path("reference").asText())
                    .isEqualTo("Encounter/MHS-CON-001");

            assertThatThrownBy(() -> source.searchAppointments("MHS-PAT-001"))
                    .isInstanceOf(ClinicalReadException.class)
                    .extracting(ex -> ((ClinicalReadException) ex).code())
                    .isEqualTo("operation_not_supported");
            assertThatThrownBy(() -> source.readAppointment("MHS-APT-001"))
                    .isInstanceOf(ClinicalReadException.class)
                    .extracting(ex -> ((ClinicalReadException) ex).code())
                    .isEqualTo("operation_not_supported");
            assertThatThrownBy(() -> source.searchObservations("MHS-PAT-001", "final"))
                    .isInstanceOf(ClinicalReadException.class)
                    .extracting(ex -> ((ClinicalReadException) ex).code())
                    .isEqualTo("operation_not_supported");
            assertThat(requests.get()).isEqualTo(beforeUnsupported);
            assertThatThrownBy(() -> source.readObservation("MHS-RES-404"))
                    .isInstanceOf(ClinicalReadException.class)
                    .extracting(ex -> ((ClinicalReadException) ex).code())
                    .isEqualTo("not_found");
            assertThat(paths.get(paths.size() - 1)).isEqualTo("/results/MHS-RES-404");
            assertThatThrownBy(() -> source.readPatient("MHS-PAT-404"))
                    .isInstanceOf(ClinicalReadException.class)
                    .extracting(ex -> ((ClinicalReadException) ex).code())
                    .isEqualTo("not_found");
        } finally {
            server.stop(0);
        }
        verifyNoInteractions(routing);
    }

    @Test
    void invalidPayloadAndClosedPortStayDistinct() {
        MiniHisClinicalSource closed = source("http://127.0.0.1:59991");
        assertThatThrownBy(() -> closed.readPatient("MHS-PAT-001"))
                .isInstanceOf(ClinicalReadException.class)
                .extracting(ex -> ((ClinicalReadException) ex).code())
                .isEqualTo("unavailable");
    }

    @Test
    void malformedPatientIsInvalidSource() throws IOException {
        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/patients/MHS-PAT-001", exchange -> {
            byte[] body = "{\"patientId\":\"MHS-PAT-001\"}".getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().set("Content-Type", "application/json");
            exchange.sendResponseHeaders(200, body.length);
            try (OutputStream output = exchange.getResponseBody()) {
                output.write(body);
            }
        });
        server.start();
        try {
            MiniHisClinicalSource source = source("http://127.0.0.1:" + server.getAddress().getPort());
            assertThatThrownBy(() -> source.readPatient("MHS-PAT-001"))
                    .isInstanceOf(ClinicalReadException.class)
                    .extracting(ex -> ((ClinicalReadException) ex).code())
                    .isEqualTo("invalid_source");
        } finally {
            server.stop(0);
        }
    }

    @Test
    void miniHisSourceIgnoresHapiAndUnsupportedDestinationsDoNotCallEitherReader() {
        MiniHisClinicalSource miniHis = new MiniHisClinicalSource() {
            @Override
            public JsonNode readPatient(String logicalId) {
                ObjectNode body = json.createObjectNode();
                body.put("destination", "mini-his");
                body.putObject("resource").put("id", logicalId);
                return body;
            }

            @Override
            public JsonNode searchPatients(String identifierSystem, String identifierValue) {
                throw new UnsupportedOperationException();
            }

            @Override
            public JsonNode readEncounter(String logicalId) {
                throw new UnsupportedOperationException();
            }

            @Override
            public JsonNode searchEncounters(String patientId, String status) {
                throw new UnsupportedOperationException();
            }

            @Override
            public JsonNode readObservation(String logicalId) {
                throw new UnsupportedOperationException();
            }

            @Override
            public JsonNode searchObservations(String patientId, String status) {
                throw new UnsupportedOperationException();
            }

            @Override
            public JsonNode readAppointment(String logicalId) {
                throw new UnsupportedOperationException();
            }

            @Override
            public JsonNode searchAppointments(String patientId) {
                throw new UnsupportedOperationException();
            }
        };
        ClinicalReadService service = new ClinicalReadService(
                routing,
                new FhirServersProperties("epic-sandbox", Map.of()),
                json,
                "mini-his",
                miniHis);
        assertThat(service.readPatient("MHS-PAT-001").path("resource").path("id").asText()).isEqualTo("MHS-PAT-001");
        verifyNoInteractions(routing);

        ClinicalReadService epic = new ClinicalReadService(
                routing,
                new FhirServersProperties("local-hapi", Map.of()),
                json,
                "epic-sandbox",
                miniHis);
        assertThatThrownBy(() -> epic.readPatient("MHS-PAT-001"))
                .isInstanceOf(ClinicalReadException.class)
                .extracting(ex -> ((ClinicalReadException) ex).code())
                .isEqualTo("destination_not_supported");
        verifyNoInteractions(routing);
    }

    private static void assertRequiredR4Elements(ObjectNode... resources) {
        FhirContext context = FhirContext.forR4Cached();
        var parser = context.newJsonParser();
        for (ObjectNode resource : resources) {
            IBaseResource parsed = parser.parseResource(resource.toString());
            RuntimeResourceDefinition definition = context.getResourceDefinition(parsed);
            for (BaseRuntimeChildDefinition child : definition.getChildren()) {
                if (child.getMin() > 0) {
                    assertThat(child.getAccessor().getValues(parsed))
                            .as(definition.getName() + "." + child.getElementName())
                            .hasSizeGreaterThanOrEqualTo(child.getMin());
                }
            }
        }
    }

    private MiniHisClinicalSource source(String baseUrl) {
        MiniHisClient client = new MiniHisClient(baseUrl, Duration.ofMillis(300), Duration.ofMillis(500), json);
        return new MiniHisRestSource(client, json);
    }

    private static String patientJson() {
        return """
                {"patientId":"MHS-PAT-001","familyName":"Quispe","givenName":"Ana","birthDate":"1984-03-12","administrativeSex":"female"}
                """;
    }

    private static String consultationJson() {
        return """
                {"consultationId":"MHS-CON-001","patientId":"MHS-PAT-001","occurredAt":"2026-09-01T15:00:00Z","reason":"Control","clinicianName":"Dra. Luz Demo","status":"completed","careClass":"ambulatory"}
                """;
    }

    private static String consultationsJson() {
        return "[" + consultationJson() + "]";
    }

    private static String resultJson() {
        return """
                {"resultId":"MHS-RES-001","consultationId":"MHS-CON-001","patientId":"MHS-PAT-001","resultType":"vital_sign","displayName":"Presion","valueText":"120","unit":"mmHg","observedAt":"2026-09-01T15:10:00Z","status":"final"}
                """;
    }
}

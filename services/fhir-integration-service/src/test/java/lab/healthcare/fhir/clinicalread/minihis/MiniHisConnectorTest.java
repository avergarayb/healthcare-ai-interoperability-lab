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
        assertThat(encounter.path("period").has("end")).isFalse();
        assertThat(observation.path("status").asText()).isEqualTo("final");
        assertThat(observation.path("subject").path("reference").asText()).isEqualTo("Patient/MHS-PAT-001");
        assertThat(observation.path("encounter").path("reference").asText()).isEqualTo("Encounter/MHS-CON-001");
        assertThat(observation.path("category").get(0).path("coding").get(0).path("code").asText()).isEqualTo("laboratory");
        assertThat(observation.path("valueQuantity").path("value").decimalValue()).isEqualByComparingTo("13.4");
        assertThat(observation.path("valueQuantity").path("unit").asText()).isEqualTo("g/dL");
        assertThat(observation.path("effectiveDateTime").asText()).isEqualTo("2026-09-01T15:10:00Z");
        assertThat(observation.path("issued").asText()).isEqualTo("2026-09-01T15:10:00Z");
        assertRequiredR4Elements(patient, encounter, observation);
    }

    @Test
    void completedConsultationCopiesTheVisitInstantToPeriodEnd() {
        MiniHisNormalizer normalizer = new MiniHisNormalizer(json);
        ObjectNode encounter = normalizer.encounter(json.createObjectNode()
                .put("consultationId", "MHS-CON-015")
                .put("patientId", "MHS-PAT-006")
                .put("occurredAt", "2026-06-01T10:00:00Z")
                .put("status", "completed")
                .put("careClass", "ambulatory"));

        assertThat(encounter.path("status").asText()).isEqualTo("finished");
        assertThat(encounter.path("period").path("start").asText()).isEqualTo("2026-06-01T10:00:00Z");
        assertThat(encounter.path("period").path("end").asText()).isEqualTo("2026-06-01T10:00:00Z");
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
                        .put("status", "amended")))
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
            if ("/patients".equals(path)) {
                String patientQuery = exchange.getRequestURI().getRawQuery();
                byte[] found = (patientQuery != null && patientQuery.contains("value=MHS-PAT-001")
                        ? "[" + patientJson() + "]"
                        : "[]").getBytes(StandardCharsets.UTF_8);
                exchange.getResponseHeaders().set("Content-Type", "application/json");
                exchange.getResponseHeaders().set("X-More-Results", "false");
                exchange.sendResponseHeaders(200, found.length);
                try (OutputStream output = exchange.getResponseBody()) {
                    output.write(found);
                }
                return;
            }
            if ("/results".equals(path)) {
                String query = exchange.getRequestURI().getRawQuery();
                if (query == null || !query.contains("patientId=MHS-PAT-001") || !query.contains("status=final")) {
                    exchange.sendResponseHeaders(400, -1);
                    return;
                }
                byte[] found = ("[" + resultJson() + "]").getBytes(StandardCharsets.UTF_8);
                exchange.getResponseHeaders().set("Content-Type", "application/json");
                exchange.getResponseHeaders().set("X-More-Results", "false");
                exchange.sendResponseHeaders(200, found.length);
                try (OutputStream output = exchange.getResponseBody()) {
                    output.write(found);
                }
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
            int beforeSearch = requests.get();
            JsonNode observations = source.searchObservations("MHS-PAT-001", "final");
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
            assertThat(paths.get(beforeObservation)).isEqualTo("/results/MHS-RES-001");
            assertThat(observation.path("resource").path("status").asText()).isEqualTo("final");
            assertThat(observation.path("resource").path("encounter").path("reference").asText())
                    .isEqualTo("Encounter/MHS-CON-001");

            assertThat(requests.get()).isEqualTo(beforeSearch + 1);
            assertThat(paths.get(paths.size() - 1)).isEqualTo("/results");
            assertThat(observations.path("collectionStatus").asText()).isEqualTo("complete");
            assertThat(observations.path("resourceType").asText()).isEqualTo("Observation");
            assertThat(observations.path("resources").get(0).path("status").asText()).isEqualTo("final");
            assertThat(observations.path("resources").get(0).path("subject").path("reference").asText())
                    .isEqualTo("Patient/MHS-PAT-001");
            assertThat(observations.path("resources").get(0).path("encounter").path("reference").asText())
                    .isEqualTo("Encounter/MHS-CON-001");
            assertThat(observations.path("resources").get(0).path("category").get(0).path("coding").get(0).path("code").asText())
                    .isEqualTo("vital-signs");
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
    void appointmentsUseSourceStatusAndDoNotConfirmTheParticipant() throws IOException {
        MiniHisNormalizer normalizer = new MiniHisNormalizer(json);
        JsonNode confirmed = normalizer.appointment(json.readTree(confirmedAppointmentJson()));
        assertThat(confirmed.path("status").asText()).isEqualTo("booked");
        assertThat(confirmed.path("participant").get(0).path("status").asText()).isEqualTo("needs-action");
        assertThat(confirmed.path("participant").get(0).path("actor").path("reference").asText())
                .isEqualTo("Patient/MHS-PAT-005");
        assertThat(confirmed.path("start").asText()).isEqualTo("2099-01-01T12:00:00Z");
        assertThatThrownBy(() -> normalizer.appointment(json.readTree(
                confirmedAppointmentJson().replace("confirmed", "arrived"))))
                .isInstanceOf(ClinicalReadException.class)
                .extracting(ex -> ((ClinicalReadException) ex).code())
                .isEqualTo("invalid_source");
        assertThatThrownBy(() -> normalizer.appointment(json.readTree(
                confirmedAppointmentJson().replace("2099-01-01T12:00:00Z", "tomorrow"))))
                .isInstanceOf(ClinicalReadException.class)
                .extracting(ex -> ((ClinicalReadException) ex).code())
                .isEqualTo("invalid_source");
        JsonNode undated = normalizer.appointment(json.readTree(
                confirmedAppointmentJson().replace(",\"start\":\"2099-01-01T12:00:00Z\"", "")));
        assertThat(undated.has("start")).isFalse();
        assertThat(undated.path("status").asText()).isEqualTo("booked");

        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/", exchange -> {
            String path = exchange.getRequestURI().getPath();
            String query = exchange.getRequestURI().getRawQuery() == null ? "" : exchange.getRequestURI().getRawQuery();
            String payload;
            String more = "false";
            if ("/appointments/MHS-APT-001".equals(path)) {
                payload = missedAppointmentJson();
            } else if ("/appointments/MHS-APT-404".equals(path)) {
                payload = null;
            } else if ("/appointments".equals(path) && query.contains("patientId=MHS-PAT-001")) {
                payload = "[]";
            } else if ("/appointments".equals(path) && query.contains("patientId=MHS-PAT-005")) {
                payload = "[" + missedAppointmentJson().replace("MHS-APT-001", "MHS-APT-003").replace("MHS-PAT-004", "MHS-PAT-005")
                        + "," + confirmedAppointmentJson() + "]";
            } else if ("/appointments".equals(path) && query.contains("patientId=MHS-PAT-009")) {
                payload = "[" + missedAppointmentJson() + "]";
            } else if ("/appointments".equals(path) && query.contains("patientId=MHS-PAT-004")) {
                payload = "[" + missedAppointmentJson() + "]";
                more = "true";
            } else {
                payload = null;
            }
            if (payload == null) {
                byte[] missing = "{\"error\":\"not_found\"}".getBytes(StandardCharsets.UTF_8);
                exchange.getResponseHeaders().set("Content-Type", "application/json");
                exchange.sendResponseHeaders(404, missing.length);
                try (OutputStream output = exchange.getResponseBody()) {
                    output.write(missing);
                }
                return;
            }
            byte[] body = payload.getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().set("Content-Type", "application/json");
            if ("/appointments".equals(path)) {
                exchange.getResponseHeaders().set("X-More-Results", more);
            }
            exchange.sendResponseHeaders(200, body.length);
            try (OutputStream output = exchange.getResponseBody()) {
                output.write(body);
            }
        });
        server.start();
        try {
            MiniHisClinicalSource source = source("http://127.0.0.1:" + server.getAddress().getPort());
            JsonNode exact = source.readAppointment("MHS-APT-001");
            JsonNode empty = source.searchAppointments("MHS-PAT-001");
            JsonNode found = source.searchAppointments("MHS-PAT-005");
            JsonNode truncated = source.searchAppointments("MHS-PAT-004");
            assertThat(exact.path("resource").path("status").asText()).isEqualTo("noshow");
            assertThat(exact.path("resource").path("participant").get(0).path("status").asText()).isEqualTo("needs-action");
            assertThat(exact.path("resource").path("participant").get(0).path("actor").path("reference").asText())
                    .isEqualTo("Patient/MHS-PAT-004");
            assertThat(empty.path("collectionStatus").asText()).isEqualTo("complete");
            assertThat(empty.path("resources")).isEmpty();
            assertThat(found.path("collectionStatus").asText()).isEqualTo("complete");
            assertThat(found.path("resources")).hasSize(2);
            assertThat(found.path("resources").get(0).path("status").asText()).isEqualTo("noshow");
            assertThat(found.path("resources").get(1).path("status").asText()).isEqualTo("booked");
            assertThat(found.path("resources").get(1).path("participant").get(0).path("status").asText()).isEqualTo("needs-action");
            assertThat(truncated.path("collectionStatus").asText()).isEqualTo("incomplete");
            assertThatThrownBy(() -> source.searchAppointments("MHS-PAT-009"))
                    .isInstanceOf(ClinicalReadException.class)
                    .extracting(ex -> ((ClinicalReadException) ex).code())
                    .isEqualTo("invalid_source");
            assertThatThrownBy(() -> source.readAppointment("MHS-APT-404"))
                    .isInstanceOf(ClinicalReadException.class)
                    .extracting(ex -> ((ClinicalReadException) ex).code())
                    .isEqualTo("not_found");
        } finally {
            server.stop(0);
        }
    }

    @Test
    void bloodPressureComponentsStayStructured() throws IOException {
        MiniHisNormalizer normalizer = new MiniHisNormalizer(json);
        JsonNode pressure = normalizer.observation(json.readTree(bloodPressureJson()));
        JsonNode hemoglobin = normalizer.observation(json.readTree(hemoglobinJson()));
        assertThat(pressure.path("valueQuantity").isMissingNode()).isTrue();
        assertThat(pressure.path("valueString").isMissingNode()).isTrue();
        assertThat(pressure.path("status").asText()).isEqualTo("final");
        assertThat(pressure.path("subject").path("reference").asText()).isEqualTo("Patient/MHS-PAT-001");
        assertThat(pressure.path("encounter").path("reference").asText()).isEqualTo("Encounter/MHS-CON-001");
        assertThat(pressure.path("category").get(0).path("coding").get(0).path("code").asText()).isEqualTo("vital-signs");
        assertThat(pressure.path("component")).hasSize(2);
        assertThat(pressure.path("component").get(0).path("code").path("text").asText()).isEqualTo("Presion sistolica");
        assertThat(pressure.path("component").get(0).path("code").path("coding").isMissingNode()).isTrue();
        assertThat(pressure.path("component").get(0).path("valueQuantity").path("value").decimalValue())
                .isEqualByComparingTo("120");
        assertThat(pressure.path("component").get(0).path("valueQuantity").path("unit").asText()).isEqualTo("mmHg");
        assertThat(pressure.path("component").get(0).path("valueQuantity").path("system").asText())
                .isEqualTo("http://unitsofmeasure.org");
        assertThat(pressure.path("component").get(0).path("valueQuantity").path("code").asText()).isEqualTo("mm[Hg]");
        assertThat(pressure.path("component").get(1).path("code").path("text").asText()).isEqualTo("Presion diastolica");
        assertThat(pressure.path("component").get(1).path("valueQuantity").path("value").decimalValue())
                .isEqualByComparingTo("80");
        assertThat(pressure.path("component").get(1).path("valueQuantity").path("code").asText()).isEqualTo("mm[Hg]");
        assertThat(hemoglobin.path("component").isMissingNode()).isTrue();
        assertThat(hemoglobin.path("valueQuantity").path("value").decimalValue()).isEqualByComparingTo("13.4");
        assertThat(hemoglobin.path("valueQuantity").path("unit").asText()).isEqualTo("g/dL");
        assertThat(hemoglobin.path("valueQuantity").path("system").asText()).isEqualTo("http://unitsofmeasure.org");
        assertThat(hemoglobin.path("valueQuantity").path("code").asText()).isEqualTo("g/dL");
        assertThatThrownBy(() -> normalizer.observation(json.readTree(bloodPressureJson().replace("\"unit\":\"mmHg\"", "\"unit\":\"\""))))
                .isInstanceOf(ClinicalReadException.class)
                .extracting(ex -> ((ClinicalReadException) ex).code())
                .isEqualTo("invalid_source");
        assertThatThrownBy(() -> normalizer.observation(json.readTree(
                bloodPressureJson().replace("\"valueDecimal\":\"120\"", "\"valueDecimal\":\"120/80\""))))
                .isInstanceOf(ClinicalReadException.class)
                .extracting(ex -> ((ClinicalReadException) ex).code())
                .isEqualTo("invalid_source");
        assertThatThrownBy(() -> normalizer.observation(json.readTree(
                bloodPressureJson().replace("\"Presion diastolica\"", "\"Presion sistolica\""))))
                .isInstanceOf(ClinicalReadException.class)
                .extracting(ex -> ((ClinicalReadException) ex).code())
                .isEqualTo("invalid_source");
        assertThatThrownBy(() -> normalizer.observation(json.readTree(
                bloodPressureJson().replace(
                        "\"components\":[{\"componentId\":\"MHS-CMP-002-1\",\"name\":\"Presion sistolica\",\"valueDecimal\":\"120\",\"unit\":\"mmHg\"},{\"componentId\":\"MHS-CMP-002-2\",\"name\":\"Presion diastolica\",\"valueDecimal\":\"80\",\"unit\":\"mmHg\"}]",
                        "\"components\":{\"componentId\":\"MHS-CMP-002-1\"}"))))
                .isInstanceOf(ClinicalReadException.class)
                .extracting(ex -> ((ClinicalReadException) ex).code())
                .isEqualTo("invalid_source");

        JsonNode parentPressure = normalizer.observation(json.readTree(resultJson()));
        assertThat(parentPressure.path("valueQuantity").path("value").decimalValue()).isEqualByComparingTo("120");
        assertThat(parentPressure.path("valueQuantity").path("unit").asText()).isEqualTo("mmHg");
        assertThat(parentPressure.path("valueQuantity").path("system").asText()).isEqualTo("http://unitsofmeasure.org");
        assertThat(parentPressure.path("valueQuantity").path("code").asText()).isEqualTo("mm[Hg]");
        JsonNode unknown = normalizer.observation(json.readTree(hemoglobinJson().replace("g/dL", "mg/dL")));
        assertThat(unknown.path("valueQuantity").path("value").decimalValue()).isEqualByComparingTo("13.4");
        assertThat(unknown.path("valueQuantity").path("unit").asText()).isEqualTo("mg/dL");
        assertThat(unknown.path("valueQuantity").path("system").isMissingNode()).isTrue();
        assertThat(unknown.path("valueQuantity").path("code").isMissingNode()).isTrue();

        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/", exchange -> {
            String path = exchange.getRequestURI().getPath();
            String query = exchange.getRequestURI().getRawQuery() == null ? "" : exchange.getRequestURI().getRawQuery();
            String payload = switch (path) {
                case "/results/MHS-RES-002" -> bloodPressureJson();
                case "/results/MHS-RES-001" -> hemoglobinJson();
                case "/results" -> query.contains("patientId=MHS-PAT-001") && query.contains("status=final")
                        ? "[" + hemoglobinJson() + "," + bloodPressureJson() + "]"
                        : "[]";
                default -> null;
            };
            if (payload == null) {
                exchange.sendResponseHeaders(404, -1);
                return;
            }
            byte[] body = payload.getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().set("Content-Type", "application/json");
            if ("/results".equals(path)) {
                exchange.getResponseHeaders().set("X-More-Results", "false");
            }
            exchange.sendResponseHeaders(200, body.length);
            try (OutputStream output = exchange.getResponseBody()) {
                output.write(body);
            }
        });
        server.start();
        try {
            MiniHisClinicalSource source = source("http://127.0.0.1:" + server.getAddress().getPort());
            JsonNode exact = source.readObservation("MHS-RES-002");
            JsonNode found = source.searchObservations("MHS-PAT-001", "final");
            assertThat(exact.path("resource").path("component")).hasSize(2);
            assertThat(exact.path("resource").path("valueQuantity").isMissingNode()).isTrue();
            assertThat(found.path("collectionStatus").asText()).isEqualTo("complete");
            assertThat(found.path("resources")).hasSize(2);
            assertThat(found.path("resources").get(0).path("valueQuantity").path("value").decimalValue())
                    .isEqualByComparingTo("13.4");
            assertThat(found.path("resources").get(1).path("component").get(0).path("valueQuantity").path("value").decimalValue())
                    .isEqualByComparingTo("120");
            assertThat(found.path("resources").get(1).path("component").get(1).path("valueQuantity").path("unit").asText())
                    .isEqualTo("mmHg");
        } finally {
            server.stop(0);
        }
    }

    @Test
    void observationSearchKeepsLimitsAndRejectsBadRows() throws IOException {
        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/results", exchange -> {
            String query = exchange.getRequestURI().getRawQuery() == null ? "" : exchange.getRequestURI().getRawQuery();
            String payload = "[]";
            String more = "false";
            int status = 200;
            if (query.contains("status=down")) {
                status = 503;
                payload = "{\"error\":\"unavailable\"}";
            } else if (query.contains("status=wrong")) {
                payload = "[{\"resultId\":\"MHS-RES-009\",\"consultationId\":\"MHS-CON-001\",\"patientId\":\"MHS-PAT-009\",\"resultType\":\"laboratory\",\"displayName\":\"Hemoglobina\",\"valueText\":\"1\",\"status\":\"final\"}]";
            } else if (query.contains("status=bad")) {
                payload = "[{\"resultId\":\"MHS-RES-009\",\"consultationId\":\"MHS-CON-001\",\"patientId\":\"MHS-PAT-001\",\"resultType\":\"laboratory\",\"displayName\":\"Hemoglobina\",\"valueText\":\"1\",\"status\":\"preliminary\"}]";
            } else if (query.contains("status=final")) {
                payload = "[" + resultJson() + "]";
                more = "true";
            }
            byte[] body = payload.getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().set("Content-Type", "application/json");
            exchange.getResponseHeaders().set("X-More-Results", more);
            exchange.sendResponseHeaders(status, body.length);
            try (OutputStream output = exchange.getResponseBody()) {
                output.write(body);
            }
        });
        server.start();
        try {
            MiniHisClinicalSource source = source("http://127.0.0.1:" + server.getAddress().getPort());
            JsonNode empty = source.searchObservations("MHS-PAT-001", "amended");
            JsonNode truncated = source.searchObservations("MHS-PAT-001", "final");
            assertThat(empty.path("collectionStatus").asText()).isEqualTo("complete");
            assertThat(empty.path("resources")).isEmpty();
            assertThat(truncated.path("collectionStatus").asText()).isEqualTo("incomplete");
            assertThat(truncated.path("resources")).hasSize(1);
            assertThat(truncated.path("resources").get(0).path("id").asText()).isEqualTo("MHS-RES-001");
            assertThatThrownBy(() -> source.searchObservations("MHS-PAT-001", "wrong"))
                    .isInstanceOf(ClinicalReadException.class)
                    .extracting(ex -> ((ClinicalReadException) ex).code())
                    .isEqualTo("invalid_source");
            assertThatThrownBy(() -> source.searchObservations("MHS-PAT-001", "bad"))
                    .isInstanceOf(ClinicalReadException.class)
                    .extracting(ex -> ((ClinicalReadException) ex).code())
                    .isEqualTo("invalid_source");
            assertThatThrownBy(() -> source.searchObservations("MHS-PAT-001", "down"))
                    .isInstanceOf(ClinicalReadException.class)
                    .extracting(ex -> ((ClinicalReadException) ex).code())
                    .isEqualTo("unavailable");
        } finally {
            server.stop(0);
        }
        MiniHisClinicalSource closed = source("http://127.0.0.1:59992");
        assertThatThrownBy(() -> closed.searchObservations("MHS-PAT-001", "final"))
                .isInstanceOf(ClinicalReadException.class)
                .extracting(ex -> ((ClinicalReadException) ex).code())
                .isEqualTo("unavailable");
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

            @Override
            public JsonNode searchServiceRequests(String patientId) {
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

    @Test
    void followUpCaseSearchKeepsTheMiniHisPatientId() throws IOException {
        List<String> paths = new CopyOnWriteArrayList<>();
        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/", exchange -> {
            String path = exchange.getRequestURI().getPath();
            paths.add(path);
            String query = exchange.getRequestURI().getRawQuery() == null ? "" : exchange.getRequestURI().getRawQuery();
            String payload = "[]";
            String more = "false";
            if (query.contains("value=SYN-FOLLOWUP-013")) {
                payload = """
                        [{"patientId":"MHS-PAT-004","familyName":"Demo","givenName":"Nora","birthDate":"1988-04-04","administrativeSex":"female","identifiers":[{"system":"https://lab.local/followup-case","value":"SYN-FOLLOWUP-013"}]}]
                        """;
            } else if (query.contains("value=SYN-FOLLOWUP-DUP")) {
                payload = """
                        [{"patientId":"MHS-PAT-004","familyName":"Demo","givenName":"Nora","birthDate":"1988-04-04","administrativeSex":"female","identifiers":[{"system":"https://lab.local/followup-case","value":"SYN-FOLLOWUP-DUP"}]},{"patientId":"MHS-PAT-005","familyName":"Demo","givenName":"Raul","birthDate":"1979-05-05","administrativeSex":"male","identifiers":[{"system":"https://lab.local/followup-case","value":"SYN-FOLLOWUP-DUP"}]}]
                        """;
            } else if (query.contains("value=SYN-FOLLOWUP-BAD")) {
                payload = """
                        [{"patientId":"MHS-PAT-004","familyName":"Demo","givenName":"Nora","birthDate":"1988-04-04","administrativeSex":"female","identifiers":[{"system":"https://lab.local/followup-case","value":"SYN-FOLLOWUP-013"},{"system":"https://lab.local/followup-case","value":"SYN-FOLLOWUP-013"}]}]
                        """;
            } else if (query.contains("value=SYN-FOLLOWUP-PAGE")) {
                more = "true";
                payload = """
                        [{"patientId":"MHS-PAT-004","familyName":"Demo","givenName":"Nora","birthDate":"1988-04-04","administrativeSex":"female","identifiers":[{"system":"https://lab.local/followup-case","value":"SYN-FOLLOWUP-PAGE"}]}]
                        """;
            }
            byte[] body = payload.getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().set("Content-Type", "application/json");
            exchange.getResponseHeaders().set("X-More-Results", more);
            exchange.sendResponseHeaders(200, body.length);
            try (OutputStream output = exchange.getResponseBody()) {
                output.write(body);
            }
        });
        server.start();
        try {
            MiniHisClinicalSource source = source("http://127.0.0.1:" + server.getAddress().getPort());
            JsonNode found = source.searchPatients("https://lab.local/followup-case", "SYN-FOLLOWUP-013");
            JsonNode missing = source.searchPatients("https://lab.local/followup-case", "SYN-FOLLOWUP-404");

            assertThat(paths).allMatch("/patients"::equals);
            assertThat(found.path("collectionStatus").asText()).isEqualTo("complete");
            assertThat(found.path("resources").get(0).path("id").asText()).isEqualTo("MHS-PAT-004");
            assertThat(found.path("resources").get(0).path("identifier")).hasSize(2);
            assertThat(found.path("resources").get(0).path("identifier").get(0).path("system").asText())
                    .isEqualTo(MiniHisNormalizer.PATIENT_SYSTEM);
            assertThat(found.path("resources").get(0).path("identifier").get(0).path("value").asText())
                    .isEqualTo("MHS-PAT-004");
            assertThat(found.path("resources").get(0).path("identifier").get(1).path("system").asText())
                    .isEqualTo("https://lab.local/followup-case");
            assertThat(found.path("resources").get(0).path("identifier").get(1).path("value").asText())
                    .isEqualTo("SYN-FOLLOWUP-013");
            assertThat(missing.path("collectionStatus").asText()).isEqualTo("complete");
            assertThat(missing.path("resources")).isEmpty();
            assertThatThrownBy(() -> source.searchPatients("https://lab.local/followup-case", "SYN-FOLLOWUP-DUP"))
                    .isInstanceOf(ClinicalReadException.class)
                    .extracting(ex -> ((ClinicalReadException) ex).code())
                    .isEqualTo("invalid_source");
            assertThatThrownBy(() -> source.searchPatients("https://lab.local/followup-case", "SYN-FOLLOWUP-BAD"))
                    .isInstanceOf(ClinicalReadException.class)
                    .extracting(ex -> ((ClinicalReadException) ex).code())
                    .isEqualTo("invalid_source");
            assertThatThrownBy(() -> source.searchPatients("https://lab.local/followup-case", "SYN-FOLLOWUP-PAGE"))
                    .isInstanceOf(ClinicalReadException.class)
                    .extracting(ex -> ((ClinicalReadException) ex).code())
                    .isEqualTo("invalid_source");
        } finally {
            server.stop(0);
        }
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

    private static String missedAppointmentJson() {
        return """
                {"appointmentId":"MHS-APT-001","patientId":"MHS-PAT-004","status":"not_attended","start":"2020-01-01T12:00:00Z"}
                """;
    }

    private static String confirmedAppointmentJson() {
        return """
                {"appointmentId":"MHS-APT-002","patientId":"MHS-PAT-005","status":"confirmed","start":"2099-01-01T12:00:00Z"}
                """;
    }

    private static String hemoglobinJson() {
        return """
                {"resultId":"MHS-RES-001","consultationId":"MHS-CON-001","patientId":"MHS-PAT-001","resultType":"laboratory","displayName":"Hemoglobina","valueText":"13.4","unit":"g/dL","observedAt":"2026-09-01T15:10:00Z","status":"final","components":[]}
                """;
    }

    private static String bloodPressureJson() {
        return """
                {"resultId":"MHS-RES-002","consultationId":"MHS-CON-001","patientId":"MHS-PAT-001","resultType":"vital_sign","displayName":"Presion arterial","valueText":"120/80","unit":"mmHg","observedAt":"2026-09-01T15:20:00Z","status":"final","components":[{"componentId":"MHS-CMP-002-1","name":"Presion sistolica","valueDecimal":"120","unit":"mmHg"},{"componentId":"MHS-CMP-002-2","name":"Presion diastolica","valueDecimal":"80","unit":"mmHg"}]}
                """;
    }

    private static String resultJson() {
        return """
                {"resultId":"MHS-RES-001","consultationId":"MHS-CON-001","patientId":"MHS-PAT-001","resultType":"vital_sign","displayName":"Presion","valueText":"120","unit":"mmHg","observedAt":"2026-09-01T15:10:00Z","status":"final"}
                """;
    }
}

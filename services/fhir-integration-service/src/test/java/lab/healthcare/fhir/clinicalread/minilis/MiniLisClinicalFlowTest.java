package lab.healthcare.fhir.clinicalread.minilis;

import lab.healthcare.fhir.clinicalread.ClinicalReadException;
import lab.healthcare.fhir.clinicalread.ClinicalReadService;
import lab.healthcare.fhir.clinicalread.minihis.MiniHisClinicalSource;
import lab.healthcare.fhir.routing.RoutingService;
import lab.healthcare.fhir.server.FhirServersProperties;
import lab.healthcare.minilis.MiniLisApplication;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.springframework.boot.SpringApplication;
import org.springframework.context.ConfigurableApplicationContext;
import org.testcontainers.containers.PostgreSQLContainer;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.Map;

import ca.uhn.fhir.context.FhirContext;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verifyNoInteractions;

class MiniLisClinicalFlowTest {

    private static final String TOKEN = "lab-mini-lis-dev";
    private static PostgreSQLContainer<?> postgres;
    private static ConfigurableApplicationContext lis;
    private static ClinicalReadService clinicalRead;
    private static RoutingService routing;

    @BeforeAll
    static void startLaboratory() {
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
                "mini-lis.service-token", TOKEN));
        lis = application.run("--server.port=0", "--server.address=127.0.0.1");
        String port = lis.getEnvironment().getProperty("local.server.port");
        ObjectMapper json = new ObjectMapper();
        MiniLisRestSource source = new MiniLisRestSource(
                new MiniLisClient("http://127.0.0.1:" + port, TOKEN, Duration.ofSeconds(2), Duration.ofSeconds(5), json),
                json);
        routing = mock(RoutingService.class);
        clinicalRead = new ClinicalReadService(
                routing,
                new FhirServersProperties("local-hapi", Map.of()),
                json,
                "mini-lis",
                (MiniHisClinicalSource) null,
                source);
    }

    @AfterAll
    static void stopLaboratory() {
        if (lis != null) {
            lis.close();
        }
        if (postgres != null) {
            postgres.stop();
        }
    }

    @Test
    void seededResultIsReadAsFhirFromTheRunningLaboratory() {
        JsonNode report = clinicalRead.readDiagnosticReport("MLS-ORD-002");
        assertThat(report.path("destination").asText()).isEqualTo("mini-lis");
        assertThat(report.path("resource").path("status").asText()).isEqualTo("final");
        assertThat(report.path("resource").path("result").get(0).path("reference").asText())
                .isEqualTo("Observation/MLS-RES-002");
        assertThat(report.path("resource").path("code").path("coding").get(0).path("system").asText())
                .isEqualTo(MiniLisNormalizer.TEST_SYSTEM);
        assertThat(report.path("resource").toString()).doesNotContain("loinc");

        JsonNode observations = clinicalRead.searchObservations("MLS-PAT-002", "final");
        assertThat(observations.path("collectionStatus").asText()).isEqualTo("complete");
        assertThat(observations.path("resources").get(0).path("valueQuantity").path("value").decimalValue())
                .isEqualByComparingTo("13.5");
        assertThat(observations.path("resources").get(0).path("subject").path("reference").asText())
                .isEqualTo("Patient/MLS-PAT-002");
        assertThat(observations.path("resources").get(0).path("basedOn").get(0).path("reference").asText())
                .isEqualTo("ServiceRequest/MLS-ORD-002");
        FhirContext.forR4().newJsonParser().parseResource(
                org.hl7.fhir.r4.model.Observation.class,
                observations.path("resources").get(0).toString());
        verifyNoInteractions(routing);
    }

    @Test
    void aResultWrittenToMiniLisIsTheResultReturnedAsFhir() throws Exception {
        String base = "http://127.0.0.1:" + lis.getEnvironment().getProperty("local.server.port");
        HttpClient http = HttpClient.newHttpClient();
        String patientBody = """
                {"organizationId":"org-mini-lis","externalId":"EXT-PAT-FLOW","familyName":"Salazar","givenName":"Ines","birthDate":"1988-04-04","administrativeSex":"female"}
                """;
        String patientJson = post(http, base + "/patients", patientBody);
        String patientId = patientJson.replaceAll(".*\"patientId\":\"([^\"]+)\".*", "$1");
        String orderJson = post(http, base + "/orders", """
                {"patientId":"%s","requestingOrganizationId":"org-mini-his","externalRequestId":"EXT-REQ-FLOW","testCode":"NA","testDescription":"Sodium","requestedAt":"2026-03-01T10:00:00Z"}
                """.formatted(patientId));
        String orderId = orderJson.replaceAll(".*\"orderId\":\"([^\"]+)\".*", "$1");
        post(http, base + "/orders/" + orderId + "/results", """
                {"externalResultId":"EXT-RES-FLOW","testCode":"NA","value":"141","unit":"mmol/L","referenceRange":"135-145","resultedAt":"2026-03-01T12:00:00Z","status":"FINAL"}
                """);
        post(http, base + "/orders/" + orderId + "/completion", "");

        JsonNode request = clinicalRead.readServiceRequest(orderId);
        assertThat(request.path("resource").path("status").asText()).isEqualTo("completed");
        assertThat(request.path("resource").path("requester").path("identifier").path("value").asText())
                .isEqualTo("org-mini-his");
        JsonNode observations = clinicalRead.searchObservations(patientId, "final");
        assertThat(observations.path("resources")).hasSize(1);
        assertThat(observations.path("resources").get(0).path("valueQuantity").path("value").decimalValue())
                .isEqualByComparingTo("141");
        assertThat(observations.path("resources").get(0).path("valueQuantity").path("unit").asText()).isEqualTo("mmol/L");
        JsonNode patients = clinicalRead.searchPatients(
                "https://lab.local/mini-lis/organization/org-mini-lis/patient", "EXT-PAT-FLOW");
        assertThat(patients.path("resources")).hasSize(1);
        assertThat(patients.path("resources").get(0).path("id").asText()).isEqualTo(patientId);
        verifyNoInteractions(routing);
    }

    private static String post(HttpClient http, String url, String body) throws Exception {
        HttpRequest request = HttpRequest.newBuilder(URI.create(url))
                .header("X-Service-Token", TOKEN)
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(body))
                .build();
        HttpResponse<String> response = http.send(request, HttpResponse.BodyHandlers.ofString());
        assertThat(response.statusCode()).isBetween(200, 299);
        return response.body();
    }
}

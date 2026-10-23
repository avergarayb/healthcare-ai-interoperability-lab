package lab.healthcare.fhir.exchange;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;

import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.concurrent.atomic.AtomicReference;

import static org.assertj.core.api.Assertions.assertThat;

class MiniLisExchangeConnectorTest {

    private HttpServer server;

    @AfterEach
    void stop() {
        if (server != null) {
            server.stop(0);
        }
    }

    @Test
    void duplicateOrderIsResolvedByTheExternalRequestAndPatientLookupIgnoresTheName() throws Exception {
        AtomicReference<String> patientQuery = new AtomicReference<>();
        server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/patients", exchange -> {
            byte[] body = "[]".getBytes(StandardCharsets.UTF_8);
            if ("GET".equals(exchange.getRequestMethod())) {
                patientQuery.set(exchange.getRequestURI().getRawQuery());
            }
            if ("POST".equals(exchange.getRequestMethod())) {
                body = "{\"patientId\":\"MLS-PAT-NEW\"}".getBytes(StandardCharsets.UTF_8);
                exchange.sendResponseHeaders(201, body.length);
            } else {
                exchange.sendResponseHeaders(200, body.length);
            }
            exchange.getResponseBody().write(body);
            exchange.close();
        });
        server.createContext("/orders", exchange -> {
            byte[] body;
            int status;
            if ("POST".equals(exchange.getRequestMethod())) {
                body = "{\"error\":\"duplicate\"}".getBytes(StandardCharsets.UTF_8);
                status = 409;
            } else {
                body = "{\"orderId\":\"MLS-ORD-EXISTING\",\"patientId\":\"MLS-PAT-NEW\",\"requestingOrganizationId\":\"org-mini-his\",\"externalRequestId\":\"MHS-LAB-001\",\"testCode\":\"GLU\",\"testDescription\":\"Glucose\",\"requestedAt\":\"2026-03-01T10:00:00Z\",\"status\":\"ORDERED\"}"
                        .getBytes(StandardCharsets.UTF_8);
                status = 200;
            }
            exchange.sendResponseHeaders(status, body.length);
            exchange.getResponseBody().write(body);
            exchange.close();
        });
        server.start();
        MiniLisExchangeConnector connector = new MiniLisExchangeConnector(
                "http://127.0.0.1:" + server.getAddress().getPort(),
                "connector-test-token",
                Duration.ofSeconds(2),
                Duration.ofSeconds(5),
                new ObjectMapper());

        String patientId = connector.resolvePatient(
                "org-mini-his",
                new PatientIdentity(
                        "https://lab.local/mini-his/patient",
                        "MHS-PAT-001",
                        "Quispe",
                        "Ana",
                        LocalDate.parse("1984-03-12"),
                        "female"));
        AcceptedOrder accepted = connector.accept(new DestinationCommand(
                patientId,
                "org-mini-his",
                "MHS-LAB-001",
                "GLU",
                "Glucose",
                OffsetDateTime.parse("2026-03-01T10:00:00Z"),
                "org-mini-lis",
                "https://lab.local/mini-his/test"));

        assertThat(patientId).isEqualTo("MLS-PAT-NEW");
        assertThat(patientQuery.get()).contains("organizationId=org-mini-his").contains("externalId=MHS-PAT-001");
        assertThat(patientQuery.get()).doesNotContain("Quispe");
        assertThat(accepted.alreadyPresent()).isTrue();
        assertThat(accepted.orderId()).isEqualTo("MLS-ORD-EXISTING");
    }
}

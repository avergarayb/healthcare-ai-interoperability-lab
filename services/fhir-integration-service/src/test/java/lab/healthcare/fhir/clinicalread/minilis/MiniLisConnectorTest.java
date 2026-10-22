package lab.healthcare.fhir.clinicalread.minilis;

import lab.healthcare.fhir.clinicalread.ClinicalReadException;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;

import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.time.Duration;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class MiniLisConnectorTest {

    private HttpServer server;

    @AfterEach
    void stop() {
        if (server != null) {
            server.stop(0);
        }
    }

    @Test
    void readsAPatientFromTheProprietaryApi() throws Exception {
        server = server(200, """
                {"patientId":"MLS-PAT-002","organizationId":"org-mini-lis","externalId":"EXT-PAT-002","familyName":"Ramos","givenName":"Luis","birthDate":"1978-06-02","administrativeSex":"male"}
                """);
        MiniLisRestSource source = source();
        var body = source.readPatient("MLS-PAT-002");
        assertThat(body.path("destination").asText()).isEqualTo("mini-lis");
        assertThat(body.path("resource").path("id").asText()).isEqualTo("MLS-PAT-002");
        assertThat(body.path("resource").path("meta").path("source").asText()).isEqualTo(MiniLisNormalizer.SOURCE);
    }

    @Test
    void missingPatientIsNotFoundAndAServerErrorIsUnavailable() throws Exception {
        server = server(404, """
                {"error":"not_found"}
                """);
        assertThatThrownBy(() -> source().readPatient("MLS-PAT-404"))
                .isInstanceOf(ClinicalReadException.class)
                .hasMessage("not_found");
        server.stop(0);
        server = server(503, """
                {"error":"unavailable"}
                """);
        assertThatThrownBy(() -> source().readServiceRequest("MLS-ORD-001"))
                .isInstanceOf(ClinicalReadException.class)
                .hasMessage("unavailable");
    }

    @Test
    void aPayloadMissingRequiredFieldsIsAnInvalidSource() throws Exception {
        server = server(200, """
                {"patientId":"MLS-PAT-002"}
                """);
        assertThatThrownBy(() -> source().readPatient("MLS-PAT-002"))
                .isInstanceOf(ClinicalReadException.class)
                .hasMessage("invalid_source");
    }

    @Test
    void refusesANonLoopbackBaseUrl() {
        assertThatThrownBy(() -> new MiniLisClient(
                "http://example.test",
                "lab-mini-lis-dev",
                Duration.ofSeconds(2),
                Duration.ofSeconds(5),
                new ObjectMapper()))
                .isInstanceOf(IllegalArgumentException.class);
    }

    private MiniLisRestSource source() {
        ObjectMapper json = new ObjectMapper();
        String base = "http://127.0.0.1:" + server.getAddress().getPort();
        return new MiniLisRestSource(
                new MiniLisClient(base, "lab-mini-lis-dev", Duration.ofSeconds(2), Duration.ofSeconds(5), json),
                json);
    }

    private HttpServer server(int status, String body) throws Exception {
        HttpServer http = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        http.createContext("/", exchange -> {
            String token = exchange.getRequestHeaders().getFirst("X-Service-Token");
            if (!"lab-mini-lis-dev".equals(token)) {
                exchange.sendResponseHeaders(401, -1);
                exchange.close();
                return;
            }
            byte[] payload = body.getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().add("Content-Type", "application/json");
            exchange.sendResponseHeaders(status, payload.length);
            exchange.getResponseBody().write(payload);
            exchange.close();
        });
        http.start();
        return http;
    }
}

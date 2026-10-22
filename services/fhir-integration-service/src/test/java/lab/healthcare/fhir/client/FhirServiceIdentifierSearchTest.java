package lab.healthcare.fhir.client;

import ca.uhn.fhir.context.FhirContext;
import ca.uhn.fhir.rest.client.api.IGenericClient;
import ca.uhn.fhir.rest.client.api.ServerValidationModeEnum;
import org.hl7.fhir.r4.model.Bundle;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.URI;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.concurrent.atomic.AtomicReference;

import com.sun.net.httpserver.HttpServer;

import static org.assertj.core.api.Assertions.assertThat;

class FhirServiceIdentifierSearchTest {

    @Test
    void identifierSearchKeepsSystemValueSeparatorAndEncodesReservedUrlCharacters() throws IOException {
        AtomicReference<String> rawQuery = new AtomicReference<>();
        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/fhir/Patient", exchange -> {
            rawQuery.set(exchange.getRequestURI().getRawQuery());
            byte[] body = "{\"resourceType\":\"Bundle\",\"type\":\"searchset\",\"total\":0}"
                    .getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().set("Content-Type", "application/fhir+json; charset=UTF-8");
            exchange.sendResponseHeaders(200, body.length);
            try (OutputStream output = exchange.getResponseBody()) {
                output.write(body);
            }
        });
        server.start();
        try {
            FhirContext context = FhirContext.forR4();
            context.getRestfulClientFactory().setServerValidationMode(ServerValidationModeEnum.NEVER);
            IGenericClient client = context.newRestfulGenericClient(
                    "http://127.0.0.1:" + server.getAddress().getPort() + "/fhir");
            FhirService fhirService = new FhirService(client);

            Bundle plain = fhirService.searchPatientsByIdentifierAndCount(
                    "https://lab.local/followup-case", "SYN-DEMO-101", 25);

            assertThat(plain.getType()).isEqualTo(Bundle.BundleType.SEARCHSET);
            assertIdentifier(rawQuery.get(), "https://lab.local/followup-case", "SYN-DEMO-101");

            fhirService.searchPatientsByIdentifierAndCount(
                    "https://lab.example/sys?a=1&b=2", "CASE 100", 25);

            assertIdentifier(rawQuery.get(), "https://lab.example/sys?a=1&b=2", "CASE 100");
        } finally {
            server.stop(0);
        }
    }

    private static void assertIdentifier(String rawQuery, String system, String value) {
        assertThat(rawQuery).contains("_count=25");
        assertThat(rawQuery).doesNotContain("%5C%7C");
        assertThat(rawQuery).doesNotContain("\\|");
        String identifier = Arrays.stream(rawQuery.split("&"))
                .filter(parameter -> parameter.startsWith("identifier="))
                .map(parameter -> parameter.substring("identifier=".length()))
                .findFirst()
                .orElseThrow();
        String decoded = URLDecoder.decode(identifier, StandardCharsets.UTF_8);
        assertThat(decoded).isEqualTo(system + "|" + value);
        URI.create("http://127.0.0.1/fhir/Patient?" + rawQuery);
    }
}

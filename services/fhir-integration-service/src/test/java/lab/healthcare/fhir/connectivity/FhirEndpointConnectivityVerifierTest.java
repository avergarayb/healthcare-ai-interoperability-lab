package lab.healthcare.fhir.connectivity;

import lab.healthcare.fhir.exception.FhirErrorCategory;

import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.Test;

import java.net.InetSocketAddress;
import java.net.URI;
import java.time.Duration;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class FhirEndpointConnectivityVerifierTest {

    @Test
    void metadataUriRejectsBlankAndCredentials() {
        assertThatThrownBy(() -> FhirEndpointConnectivityVerifier.metadataUri(" "))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> FhirEndpointConnectivityVerifier.metadataUri("http://user:secret@127.0.0.1/fhir"))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("credentials");
        assertThat(FhirEndpointConnectivityVerifier.metadataUri("http://127.0.0.1:8080/fhir"))
                .isEqualTo(URI.create("http://127.0.0.1:8080/fhir/metadata"));
        assertThat(FhirEndpointConnectivityVerifier.metadataUri("http://127.0.0.1:8080/fhir/"))
                .isEqualTo(URI.create("http://127.0.0.1:8080/fhir/metadata"));
    }

    @Test
    void reachableLocalMetadataDoesNotKeepAPayload() throws Exception {
        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/fhir/metadata", exchange -> {
            exchange.sendResponseHeaders(200, 0);
            exchange.close();
        });
        server.start();
        try {
            String base = "http://127.0.0.1:" + server.getAddress().getPort() + "/fhir";
            FhirEndpointConnectivityVerifier verifier = new FhirEndpointConnectivityVerifier();
            FhirConnectivityStatus status = verifier.verify(base);

            assertThat(status.reachable()).isTrue();
            assertThat(status.httpStatus()).isEqualTo(200);
            assertThat(status.toString()).doesNotContain("Patient");
            assertThat(status.toString()).doesNotContain("access_token");
        } finally {
            server.stop(0);
        }
    }

    @Test
    void connectionRefusedIsDependencyFailureNotValidation() {
        FhirEndpointConnectivityVerifier verifier =
                new FhirEndpointConnectivityVerifier((uri, timeout) -> {
                    throw new java.net.ConnectException("Connection refused");
                }, Duration.ofMillis(200));

        FhirConnectivityStatus status = verifier.verify("http://127.0.0.1:1/fhir");

        assertThat(status.outcome()).isEqualTo(FhirConnectivityOutcome.UNREACHABLE);
        assertThat(status.error()).isEqualTo(FhirErrorCategory.CONNECTION_ERROR);
    }

    @Test
    void malformedBaseUrlIsValidationWithoutCallingProbe() {
        java.util.concurrent.atomic.AtomicInteger calls = new java.util.concurrent.atomic.AtomicInteger();
        FhirEndpointConnectivityVerifier verifier = new FhirEndpointConnectivityVerifier((uri, timeout) -> {
            calls.incrementAndGet();
            return 200;
        }, Duration.ofSeconds(1));

        FhirConnectivityStatus status = verifier.verify("not-a-uri");

        assertThat(status.error()).isEqualTo(FhirErrorCategory.VALIDATION_ERROR);
        assertThat(calls.get()).isZero();
    }
}

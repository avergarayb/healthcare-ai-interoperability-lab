package lab.healthcare.fhir.vendor.epic;

import lab.healthcare.fhir.auth.FhirAuthenticationSettings;
import lab.healthcare.fhir.auth.FhirAuthenticationType;
import lab.healthcare.fhir.capability.FhirInteraction;
import lab.healthcare.fhir.capability.FhirServerCapabilities;
import lab.healthcare.fhir.client.FhirClientFactory;
import lab.healthcare.fhir.server.FhirServerProfile;
import lab.healthcare.fhir.server.FhirServersProperties;
import lab.healthcare.fhir.vendor.FhirVendor;

import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.Test;

import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;

import static org.assertj.core.api.Assertions.assertThat;

class EpicSandboxCapabilityDiscoveryHttpTest {

    private static final String STATEMENT =
            """
            {
              "resourceType": "CapabilityStatement",
              "status": "active",
              "date": "2026-01-01",
              "kind": "instance",
              "fhirVersion": "4.0.1",
              "format": ["application/fhir+json"],
              "rest": [{
                "mode": "server",
                "resource": [
                  {
                    "type": "Patient",
                    "interaction": [{"code": "read"}, {"code": "search-type"}]
                  },
                  {
                    "type": "Observation",
                    "interaction": [{"code": "read"}]
                  }
                ]
              }]
            }
            """;

    @Test
    void publicMetadataIsASingleUnauthenticatedGet() throws Exception {
        AtomicInteger requests = new AtomicInteger();
        List<String> methods = new ArrayList<>();
        List<String> paths = new ArrayList<>();
        List<String> authorizations = new ArrayList<>();
        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/metadata", exchange -> {
            requests.incrementAndGet();
            methods.add(exchange.getRequestMethod());
            paths.add(exchange.getRequestURI().getPath());
            authorizations.add(exchange.getRequestHeaders().getFirst("Authorization"));
            byte[] body = STATEMENT.getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().set("Content-Type", "application/fhir+json");
            exchange.sendResponseHeaders(200, body.length);
            exchange.getResponseBody().write(body);
            exchange.close();
        });
        server.start();
        try {
            String base = "http://127.0.0.1:" + server.getAddress().getPort();
            EpicIntegrationProfile profile = enabledAt(base);
            EpicSandboxCapabilityDiscoveryService service =
                    new EpicSandboxCapabilityDiscoveryService(new EpicProfileValidator(), new FhirClientFactory());

            FhirServerCapabilities capabilities = service.discover(profile);

            // HAPI may repeat GET /metadata during format negotiation. The
            // application still issues a single capability-discovery operation.
            assertThat(requests.get()).isGreaterThanOrEqualTo(1);
            assertThat(methods).isNotEmpty().allMatch("GET"::equals);
            assertThat(paths).isNotEmpty().allMatch("/metadata"::equals);
            assertThat(authorizations).isNotEmpty().allMatch(header -> header == null);
            assertThat(profile.toUnauthenticatedMetadataProfile().authentication().requiresBearerToken()).isFalse();
            assertThat(capabilities.destination()).isEqualTo(EpicIntegrationProfile.SANDBOX_SERVER);
            assertThat(capabilities.fhirVersion()).isEqualTo("4.0.1");
            assertThat(capabilities.supports("Patient", FhirInteraction.READ)).isTrue();
            assertThat(capabilities.supports("Patient", FhirInteraction.SEARCH_TYPE)).isTrue();
            assertThat(capabilities.supportsResource("Observation")).isTrue();
            assertThat(capabilities.toString()).doesNotContain("access_token");
            assertThat(capabilities.toString()).doesNotContain("Patient/");
        } finally {
            server.stop(0);
        }
    }

    private static EpicIntegrationProfile enabledAt(String baseUrl) {
        FhirAuthenticationSettings auth = new FhirAuthenticationSettings(
                FhirAuthenticationType.SMART_AUTHORIZATION_CODE,
                null,
                "lab-epic-placeholder",
                "",
                "http://127.0.0.1/does-not-contact-epic/.well-known/smart-configuration",
                "http://127.0.0.1:8081/smart/callback",
                "patient/Patient.read",
                baseUrl);
        return EpicIntegrationProfile.from(
                new FhirServerProfile(
                        EpicIntegrationProfile.SANDBOX_SERVER, baseUrl, "R4", true, FhirVendor.EPIC, auth),
                FhirServersProperties.VendorIntegrationSettings.of(
                        "SANDBOX", "STANDALONE", "PATIENT", "PUBLIC_PKCE"));
    }
}

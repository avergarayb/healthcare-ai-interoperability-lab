package lab.healthcare.fhir.routing;

import lab.healthcare.fhir.auth.FhirAuthenticationType;
import lab.healthcare.fhir.auth.oauth2.OAuth2TokenClient;
import lab.healthcare.fhir.client.FhirAccessTokenProviders;
import lab.healthcare.fhir.client.FhirClientFactory;
import lab.healthcare.fhir.observability.InMemoryFhirMetricsRecorder;
import lab.healthcare.fhir.observability.LoggingFhirAuditRecorder;
import lab.healthcare.fhir.server.FhirServerProfile;
import lab.healthcare.fhir.server.FhirServerProfileRegistry;
import lab.healthcare.fhir.server.FhirServersProperties;
import lab.healthcare.fhir.smart.AuthorizationCodeClient;
import lab.healthcare.fhir.smart.SmartConfigurationClient;

import ca.uhn.fhir.context.FhirContext;
import ca.uhn.fhir.rest.client.api.IGenericClient;
import org.hl7.fhir.r4.model.Observation;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.Clock;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class RoutingServiceTest {

    private final FhirClientFactory factory = new FhirClientFactory();
    private final FhirAccessTokenProviders tokenProviders = new FhirAccessTokenProviders(
            new OAuth2TokenClient(),
            new SmartConfigurationClient(),
            new AuthorizationCodeClient(),
            Clock.systemUTC());

    @Mock
    private FhirClientFactory mockFactory;

    @Mock
    private IGenericClient mockClient;

    @Test
    void resolvesEnabledLocalHapiProfileAndClient() {
        RoutingRequest request = RoutingRequest.readPatient("local-hapi", "patient-001");
        RoutingService routing = routing(twoServers());

        FhirServerProfile profile = routing.resolve(request);
        IGenericClient client = routing.client(request);

        assertThat(profile.name()).isEqualTo("local-hapi");
        assertThat(profile.enabled()).isTrue();
        assertThat(profile.baseUrl()).isEqualTo("http://localhost:8080/fhir");
        assertThat(profile.authentication().type()).isEqualTo(FhirAuthenticationType.NONE);
        assertThat(client.getServerBase()).isEqualTo(profile.baseUrl());
    }

    @Test
    void unknownDestinationFailsExplicitly() {
        RoutingService routing = routing(twoServers());

        assertThatThrownBy(() -> routing.resolve(RoutingRequest.readPatient("does-not-exist", "patient-001")))
                .isInstanceOf(RoutingException.class)
                .hasMessageContaining("does-not-exist")
                .hasMessageContaining("FHIR destination not found");
    }

    @Test
    void disabledDestinationFailsWithoutFallback() {
        RoutingService routing = routing(twoServers());

        assertThatThrownBy(() -> routing.client(RoutingRequest.readPatient("example-org", "patient-001")))
                .isInstanceOf(RoutingException.class)
                .hasMessageContaining("example-org")
                .hasMessageContaining("disabled");
    }

    @Test
    void oauthDestinationUsesConfiguredBaseUrlWithoutCallingTheServer() {
        RoutingRequest request = RoutingRequest.readPatient("secured-lab", "patient-001");
        RoutingService routing = routing(securedLabEnabled());

        FhirServerProfile profile = routing.resolve(request);
        IGenericClient client = routing.client(request);

        assertThat(profile.name()).isEqualTo("secured-lab");
        assertThat(profile.authentication().isClientCredentials()).isTrue();
        assertThat(client.getServerBase()).isEqualTo("http://localhost:8180/fhir");
    }

    @Test
    void factoryCreatesClientForResolvedProfile() {
        FhirContext context = FhirContext.forR4();
        when(mockFactory.createContext(any(FhirServerProfile.class))).thenReturn(context);
        when(mockFactory.createClient(eq(context), any(FhirServerProfile.class), any())).thenReturn(mockClient);
        RoutingService routing = new RoutingService(
                new FhirServerProfileRegistry(twoServers()),
                mockFactory,
                tokenProviders,
                new LoggingFhirAuditRecorder(),
                new InMemoryFhirMetricsRecorder());
        RoutingRequest request = RoutingRequest.readPatient("local-hapi", "patient-001");

        IGenericClient client = routing.client(request);

        assertThat(client).isSameAs(mockClient);
        verify(mockFactory).createContext(any(FhirServerProfile.class));
        verify(mockFactory).createClient(eq(context), any(FhirServerProfile.class), any());
    }

    @Test
    void readRequiresPatientResource() {
        RoutingService routing = routing(twoServers());
        Observation observation = new Observation();
        observation.setId("obs-001");

        assertThatThrownBy(() -> routing.readPatient(new RoutingRequest("local-hapi", observation)))
                .isInstanceOf(RoutingException.class)
                .hasMessageContaining("Patient");
    }

    private RoutingService routing(FhirServersProperties properties) {
        return new RoutingService(
                new FhirServerProfileRegistry(properties),
                factory,
                tokenProviders,
                new LoggingFhirAuditRecorder(),
                new InMemoryFhirMetricsRecorder());
    }

    private static FhirServersProperties twoServers() {
        return new FhirServersProperties(
                "local-hapi",
                Map.of(
                        "local-hapi", new FhirServersProperties.ServerSettings(
                                "http://localhost:8080/fhir", "R4", true, null),
                        "example-org", new FhirServersProperties.ServerSettings(
                                "https://example.org/fhir", "R4", false, null)));
    }

    private static FhirServersProperties securedLabEnabled() {
        return new FhirServersProperties(
                "secured-lab",
                Map.of(
                        "secured-lab",
                        new FhirServersProperties.ServerSettings(
                                "http://localhost:8180/fhir",
                                "R4",
                                true,
                                new FhirServersProperties.AuthenticationSettings(
                                        "OAUTH2_CLIENT_CREDENTIALS",
                                        "http://localhost:9090/oauth/token",
                                        "lab-client",
                                        "lab-secret",
                                        null,
                                        null,
                                        null,
                                        null))));
    }
}

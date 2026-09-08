package lab.healthcare.fhir.vendor.epic;

import lab.healthcare.fhir.auth.FhirAuthenticationType;
import lab.healthcare.fhir.capability.FhirCapabilityException;
import lab.healthcare.fhir.capability.FhirInteraction;
import lab.healthcare.fhir.capability.FhirServerCapabilities;
import lab.healthcare.fhir.client.FhirClientFactory;
import lab.healthcare.fhir.exception.FhirClientException;
import lab.healthcare.fhir.exception.FhirErrorCategory;
import lab.healthcare.fhir.exception.FhirErrorDetails;
import lab.healthcare.fhir.server.FhirServerProfile;
import lab.healthcare.fhir.server.FhirServersProperties;
import lab.healthcare.fhir.vendor.FhirVendor;

import ca.uhn.fhir.context.FhirContext;
import ca.uhn.fhir.rest.client.api.IGenericClient;
import org.hl7.fhir.r4.model.CapabilityStatement;
import org.hl7.fhir.r4.model.Enumerations;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.mockito.Answers.RETURNS_DEEP_STUBS;

@ExtendWith(MockitoExtension.class)
class EpicSandboxCapabilityDiscoveryServiceTest {

    @Mock
    private FhirClientFactory clientFactory;

    @Mock(answer = RETURNS_DEEP_STUBS)
    private IGenericClient fhirClient;

    @Test
    void disabledProfileDoesNotCreateAClient() {
        EpicSandboxCapabilityDiscoveryService service = service();

        assertThatThrownBy(() -> service.discover(EpicIntegrationProfileTest.completePublicPkce()))
                .isInstanceOf(EpicProfileException.class)
                .hasMessageContaining("disabled")
                .hasMessageNotContaining("access_token");
        verify(clientFactory, never()).createContext(any());
        verify(clientFactory, never()).createClient(any(), any());
    }

    @Test
    void productionIsNotDiscovered() {
        EpicIntegrationProfile profile = EpicIntegrationProfile.from(
                EpicIntegrationProfileTest.epicServer(true, EpicIntegrationProfileTest.smartAuth()),
                FhirServersProperties.VendorIntegrationSettings.of(
                        "PRODUCTION", "STANDALONE", "PATIENT", "PUBLIC_PKCE"));

        assertThatThrownBy(() -> service().discover(profile))
                .isInstanceOf(EpicProfileException.class)
                .hasMessageContaining("SANDBOX")
                .hasMessageNotContaining("access_token");
        verify(clientFactory, never()).createClient(any(), any());
    }

    @Test
    void discoverUsesUnauthenticatedClientAndExistingInterpreter() {
        FhirContext context = FhirContext.forR4();
        when(clientFactory.createContext(any())).thenReturn(context);
        when(clientFactory.createClient(any(), any())).thenReturn(fhirClient);
        when(fhirClient.capabilities().ofType(CapabilityStatement.class).execute())
                .thenReturn(epicShapedStatement());
        EpicIntegrationProfile profile = EpicIntegrationProfileTest.enabledCompletePublicPkce();

        FhirServerCapabilities capabilities = service().discover(profile);

        ArgumentCaptor<FhirServerProfile> profileCaptor = ArgumentCaptor.forClass(FhirServerProfile.class);
        verify(clientFactory).createClient(any(), profileCaptor.capture());
        FhirServerProfile unauthenticated = profileCaptor.getValue();
        assertThat(unauthenticated.name()).isEqualTo(EpicIntegrationProfile.SANDBOX_SERVER);
        assertThat(unauthenticated.baseUrl()).isEqualTo(EpicSandboxEndpoints.FHIR_R4_BASE);
        assertThat(unauthenticated.vendor()).isEqualTo(FhirVendor.EPIC);
        assertThat(unauthenticated.authentication().type()).isEqualTo(FhirAuthenticationType.NONE);
        assertThat(unauthenticated.authentication().requiresBearerToken()).isFalse();
        assertThat(capabilities.destination()).isEqualTo(EpicIntegrationProfile.SANDBOX_SERVER);
        assertThat(capabilities.fhirVersion()).isEqualTo("4.0.1");
        assertThat(capabilities.supportsResource("Patient")).isTrue();
        assertThat(capabilities.supportsResource("Observation")).isTrue();
        assertThat(capabilities.supports("Patient", FhirInteraction.READ)).isTrue();
        assertThat(capabilities.supports("Patient", FhirInteraction.SEARCH_TYPE)).isTrue();
        assertThat(capabilities.supports("Patient", FhirInteraction.UPDATE)).isFalse();
        assertThat(capabilities.toString()).doesNotContain("access_token");
        assertThat(capabilities.toString()).doesNotContain("Patient/");
        assertThat(EpicKnownApiSurface.assumesEveryR4Resource()).isFalse();
    }

    @Test
    void authenticationFailureIsPropagatedWithoutInventingAToken() {
        FhirContext context = FhirContext.forR4();
        when(clientFactory.createContext(any())).thenReturn(context);
        when(clientFactory.createClient(any(), any())).thenReturn(fhirClient);
        when(fhirClient.capabilities().ofType(CapabilityStatement.class).execute())
                .thenThrow(new FhirClientException(
                        FhirErrorDetails.of(FhirErrorCategory.AUTHENTICATION_ERROR, 401), null));

        assertThatThrownBy(() -> service().discover(EpicIntegrationProfileTest.enabledCompletePublicPkce()))
                .isInstanceOf(FhirClientException.class)
                .satisfies(ex -> {
                    FhirClientException failure = (FhirClientException) ex;
                    assertThat(failure.category()).isEqualTo(FhirErrorCategory.AUTHENTICATION_ERROR);
                    assertThat(failure.details().status()).isEqualTo(401);
                    assertThat(failure.getMessage()).doesNotContain("access_token");
                });
    }

    @Test
    void invalidCapabilityDocumentIsPropagated() {
        FhirContext context = FhirContext.forR4();
        when(clientFactory.createContext(any())).thenReturn(context);
        when(clientFactory.createClient(any(), any())).thenReturn(fhirClient);
        when(fhirClient.capabilities().ofType(CapabilityStatement.class).execute())
                .thenReturn(new CapabilityStatement());

        assertThatThrownBy(() -> service().discover(EpicIntegrationProfileTest.enabledCompletePublicPkce()))
                .isInstanceOf(FhirCapabilityException.class)
                .hasMessageContaining("fhirVersion")
                .hasMessageNotContaining("access_token");
    }

    private EpicSandboxCapabilityDiscoveryService service() {
        return new EpicSandboxCapabilityDiscoveryService(new EpicProfileValidator(), clientFactory);
    }

    /**
     * Synthetic CapabilityStatement shape. Hosts stay on the configured profile
     * identifier, not a second invented endpoint.
     */
    static CapabilityStatement epicShapedStatement() {
        CapabilityStatement statement = new CapabilityStatement();
        statement.setFhirVersion(Enumerations.FHIRVersion._4_0_1);
        statement.setPublisher("Epic");
        CapabilityStatement.CapabilityStatementRestComponent rest = statement.addRest();
        rest.setMode(CapabilityStatement.RestfulCapabilityMode.SERVER);
        CapabilityStatement.CapabilityStatementRestResourceComponent patient = rest.addResource();
        patient.setType("Patient");
        patient.addInteraction().setCode(CapabilityStatement.TypeRestfulInteraction.READ);
        patient.addInteraction().setCode(CapabilityStatement.TypeRestfulInteraction.SEARCHTYPE);
        CapabilityStatement.CapabilityStatementRestResourceComponent observation = rest.addResource();
        observation.setType("Observation");
        observation.addInteraction().setCode(CapabilityStatement.TypeRestfulInteraction.READ);
        return statement;
    }
}

package lab.healthcare.fhir.vendor.oracle;

import lab.healthcare.fhir.auth.FhirAuthenticationType;
import lab.healthcare.fhir.capability.FhirCapabilityDiscoveryService;
import lab.healthcare.fhir.capability.FhirInteraction;
import lab.healthcare.fhir.capability.FhirServerCapabilities;
import lab.healthcare.fhir.client.FhirClientFactory;
import lab.healthcare.fhir.connectivity.FhirEndpointConnectivityVerifier;
import lab.healthcare.fhir.exception.FhirErrorCategory;
import lab.healthcare.fhir.server.FhirDeploymentEnvironment;
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
class OracleSandboxCapabilityDiscoveryServiceTest {

    @Mock
    private FhirEndpointConnectivityVerifier verifier;

    @Mock
    private FhirClientFactory clientFactory;

    @Mock(answer = RETURNS_DEEP_STUBS)
    private IGenericClient fhirClient;

    @Test
    void disabledProfileDoesNotCreateAClient() {
        OracleSandboxCapabilityDiscoveryService service = service();

        OracleSandboxReadiness readiness = service.inspect(OracleHealthIntegrationProfileTest.completePublicPkce());

        assertThat(readiness.state()).isEqualTo(OracleSandboxReadinessState.DISABLED);
        assertThatThrownBy(() -> service.discover(OracleHealthIntegrationProfileTest.completePublicPkce()))
                .isInstanceOf(OracleHealthProfileException.class)
                .hasMessageContaining("disabled")
                .hasMessageNotContaining("access_token");
        verify(clientFactory, never()).createContext(any());
        verify(clientFactory, never()).createClient(any(), any());
        verify(verifier, never()).verify(any());
    }

    @Test
    void productionIsConfiguredNotDiscovered() {
        OracleHealthIntegrationProfile profile = OracleHealthIntegrationProfile.from(
                OracleHealthIntegrationProfileTest.oracleServer(true, OracleHealthIntegrationProfileTest.smartAuth()),
                FhirServersProperties.VendorIntegrationSettings.of(
                        "PRODUCTION", "STANDALONE", "PATIENT", "PUBLIC_PKCE"));
        OracleSandboxCapabilityDiscoveryService service = service();

        OracleSandboxReadiness readiness = service.inspect(profile);

        assertThat(readiness.state()).isEqualTo(OracleSandboxReadinessState.CONFIGURED);
        assertThat(readiness.deploymentEnvironment()).isEqualTo(FhirDeploymentEnvironment.PRODUCTION);
        assertThatThrownBy(() -> service.discover(profile))
                .isInstanceOf(OracleHealthProfileException.class)
                .hasMessageContaining("SANDBOX");
        verify(clientFactory, never()).createClient(any(), any());
    }

    @Test
    void invalidConfigurationDoesNotCreateAClient() {
        OracleSandboxCapabilityDiscoveryService service = service();
        OracleHealthIntegrationProfile profile = enabledMissingClientId();

        OracleSandboxReadiness readiness = service.inspect(profile);

        assertThat(readiness.state()).isEqualTo(OracleSandboxReadinessState.INVALID_CONFIGURATION);
        assertThat(readiness.error()).isEqualTo(FhirErrorCategory.VALIDATION_ERROR);
        assertThatThrownBy(() -> service.discover(profile))
                .isInstanceOf(OracleHealthProfileException.class)
                .hasMessageNotContaining("access_token");
        verify(clientFactory, never()).createClient(any(), any());
    }

    @Test
    void discoverUsesUnauthenticatedClientAndExistingInterpreter() {
        FhirContext context = FhirContext.forR4();
        when(clientFactory.createContext(any())).thenReturn(context);
        when(clientFactory.createClient(any(), any())).thenReturn(fhirClient);
        when(fhirClient.capabilities().ofType(CapabilityStatement.class).execute())
                .thenReturn(oracleShapedStatement());
        OracleHealthIntegrationProfile profile = OracleHealthIntegrationProfileTest.completePublicPkceEnabled();

        FhirServerCapabilities capabilities = service().discover(profile);

        ArgumentCaptor<FhirServerProfile> profileCaptor = ArgumentCaptor.forClass(FhirServerProfile.class);
        verify(clientFactory).createClient(any(), profileCaptor.capture());
        FhirServerProfile unauthenticated = profileCaptor.getValue();
        assertThat(unauthenticated.name()).isEqualTo(OracleHealthIntegrationProfile.SANDBOX_SERVER);
        assertThat(unauthenticated.baseUrl()).isEqualTo(OracleHealthIntegrationProfileTest.SYNTHETIC_BASE);
        assertThat(unauthenticated.vendor()).isEqualTo(FhirVendor.ORACLE_HEALTH);
        assertThat(unauthenticated.authentication().type()).isEqualTo(FhirAuthenticationType.NONE);
        assertThat(unauthenticated.authentication().requiresBearerToken()).isFalse();
        assertThat(capabilities.destination()).isEqualTo(OracleHealthIntegrationProfile.SANDBOX_SERVER);
        assertThat(capabilities.fhirVersion()).isEqualTo("4.0.1");
        assertThat(capabilities.softwareName()).isEmpty();
        assertThat(capabilities.implementationUrl()).isEqualTo(OracleHealthIntegrationProfileTest.SYNTHETIC_BASE);
        assertThat(capabilities.supportsResource("Patient")).isTrue();
        assertThat(capabilities.supportsResource("Observation")).isTrue();
        assertThat(capabilities.supportsResource("Account")).isTrue();
        assertThat(capabilities.supports("Patient", FhirInteraction.READ)).isTrue();
        assertThat(capabilities.supports("Patient", FhirInteraction.SEARCH_TYPE)).isTrue();
        assertThat(capabilities.supports("Patient", FhirInteraction.CREATE)).isTrue();
        assertThat(capabilities.supports("Patient", FhirInteraction.UPDATE)).isFalse();
        assertThat(capabilities.supports("Patient", FhirInteraction.DELETE)).isFalse();
        assertThat(capabilities.resource("Patient").orElseThrow().interactions())
                .doesNotContain(FhirInteraction.UPDATE);
        assertThat(capabilities.toString()).doesNotContain("access_token");
        assertThat(capabilities.toString()).doesNotContain("Patient/");
        assertThat(OracleHealthKnownApiSurface.assumesEveryR4Resource()).isFalse();
        verify(verifier, never()).verify(any());
    }

    @Test
    void interpretOmitsPatchAndDoesNotInventMissingResources() {
        FhirServerCapabilities capabilities =
                new FhirCapabilityDiscoveryService().interpret("oracle-health-sandbox", oracleShapedStatement());

        assertThat(capabilities.supports("Patient", FhirInteraction.READ)).isTrue();
        assertThat(capabilities.resource("Patient").orElseThrow().interactions())
                .containsExactly(
                        FhirInteraction.READ, FhirInteraction.SEARCH_TYPE, FhirInteraction.CREATE);
        assertThat(capabilities.supportsResource("Medication")).isFalse();
        assertThat(capabilities.supportsResource("Claim")).isFalse();
    }

    private OracleSandboxCapabilityDiscoveryService service() {
        return new OracleSandboxCapabilityDiscoveryService(
                new OracleSandboxReadinessService(new OracleSandboxProfileValidator(), verifier),
                new OracleSandboxProfileValidator(),
                clientFactory);
    }

    private static OracleHealthIntegrationProfile enabledMissingClientId() {
        lab.healthcare.fhir.auth.FhirAuthenticationSettings auth =
                new lab.healthcare.fhir.auth.FhirAuthenticationSettings(
                        lab.healthcare.fhir.auth.FhirAuthenticationType.SMART_AUTHORIZATION_CODE,
                        null,
                        "",
                        "",
                        "http://127.0.0.1/does-not-contact-oracle/.well-known/smart-configuration",
                        "http://127.0.0.1:8081/smart/callback",
                        "patient/Patient.read",
                        OracleHealthIntegrationProfileTest.SYNTHETIC_BASE);
        return OracleHealthIntegrationProfile.from(
                OracleHealthIntegrationProfileTest.oracleServer(true, auth), null);
    }

    /**
     * Shape observed on the Oracle Code sandbox CapabilityStatement: empty software
     * name, SMART security ignored by the internal model, Patient read/search-type/
     * create/patch, and a subset of R4 resources. Hosts stay synthetic.
     */
    static CapabilityStatement oracleShapedStatement() {
        CapabilityStatement statement = new CapabilityStatement();
        statement.setFhirVersion(Enumerations.FHIRVersion._4_0_1);
        statement.setPublisher("Oracle Health");
        statement.getImplementation().setUrl(OracleHealthIntegrationProfileTest.SYNTHETIC_BASE);
        CapabilityStatement.CapabilityStatementRestComponent rest = statement.addRest();
        rest.setMode(CapabilityStatement.RestfulCapabilityMode.SERVER);
        rest.getSecurity().setCors(true);
        addResource(rest, "Account", CapabilityStatement.TypeRestfulInteraction.READ);
        CapabilityStatement.CapabilityStatementRestResourceComponent patient = rest.addResource();
        patient.setType("Patient");
        patient.addInteraction().setCode(CapabilityStatement.TypeRestfulInteraction.READ);
        patient.addInteraction().setCode(CapabilityStatement.TypeRestfulInteraction.SEARCHTYPE);
        patient.addInteraction().setCode(CapabilityStatement.TypeRestfulInteraction.CREATE);
        patient.addInteraction().setCode(CapabilityStatement.TypeRestfulInteraction.PATCH);
        addResource(rest, "Observation", CapabilityStatement.TypeRestfulInteraction.READ);
        return statement;
    }

    private static void addResource(
            CapabilityStatement.CapabilityStatementRestComponent rest,
            String type,
            CapabilityStatement.TypeRestfulInteraction interaction) {
        CapabilityStatement.CapabilityStatementRestResourceComponent resource = rest.addResource();
        resource.setType(type);
        resource.addInteraction().setCode(interaction);
    }
}

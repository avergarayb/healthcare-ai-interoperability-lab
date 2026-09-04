package lab.healthcare.fhir.vendor.oracle;

import lab.healthcare.fhir.auth.AccessToken;
import lab.healthcare.fhir.auth.IssuedAccessTokenProvider;
import lab.healthcare.fhir.capability.FhirCapabilityDiscoveryService;
import lab.healthcare.fhir.capability.FhirServerCapabilities;
import lab.healthcare.fhir.connectivity.FhirEndpointConnectivityVerifier;
import lab.healthcare.fhir.server.FhirServersProperties;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotAssembler;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotOutcome;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotResourceStatus;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotResult;

import org.hl7.fhir.r4.model.CapabilityStatement;
import org.hl7.fhir.r4.model.Enumerations;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class OracleSandboxClinicalSnapshotServiceTest {

    private static final Clock CLOCK = Clock.fixed(Instant.parse("2026-09-04T03:00:00Z"), ZoneOffset.UTC);
    private static final String SECRET = "oracle-live-access-token";
    private static final String PATIENT_ID = "lab-configured-patient";

    @Mock
    private FhirEndpointConnectivityVerifier verifier;

    @Mock
    private OracleSandboxAuthenticationService authenticationService;

    @Mock
    private OracleSandboxCapabilityDiscoveryService capabilityDiscovery;

    @Mock
    private ClinicalSnapshotAssembler assembler;

    @Test
    void disabledProfileDoesNotCallOracle() {
        ClinicalSnapshotResult result = service().assemble(OracleHealthIntegrationProfileTest.completePublicPkce());

        assertThat(result.outcome()).isEqualTo(ClinicalSnapshotOutcome.AUTHENTICATION_REQUIRED);
        verify(authenticationService, never()).issuedProviderIfPresent();
        verify(capabilityDiscovery, never()).discover(any());
        verify(assembler, never()).assemble(any(), any(), any(), any());
        verify(verifier, never()).verify(any());
    }

    @Test
    void missingPatientIdIsContextNotConfiguredWithoutHttp() {
        ClinicalSnapshotResult result =
                service().assemble(OracleHealthIntegrationProfileTest.completePublicPkceEnabled());

        assertThat(result.outcome()).isEqualTo(ClinicalSnapshotOutcome.PATIENT_CONTEXT_NOT_CONFIGURED);
        verify(authenticationService, never()).issuedProviderIfPresent();
        verify(capabilityDiscovery, never()).discover(any());
        verify(assembler, never()).assemble(any(), any(), any(), any());
    }

    @Test
    void missingTokenIsAuthenticationRequiredWithoutHttp() {
        when(authenticationService.issuedProviderIfPresent()).thenReturn(Optional.empty());

        ClinicalSnapshotResult result = service().assemble(enabledWithPatient(PATIENT_ID));

        assertThat(result.outcome()).isEqualTo(ClinicalSnapshotOutcome.AUTHENTICATION_REQUIRED);
        assertThat(result.detail()).contains("No usable access token");
        verify(capabilityDiscovery, never()).discover(any());
        verify(assembler, never()).assemble(any(), any(), any(), any());
    }

    @Test
    void expiredTokenIsAuthenticationRequiredWithoutHttp() {
        when(authenticationService.issuedProviderIfPresent())
                .thenReturn(Optional.of(new IssuedAccessTokenProvider(
                        new AccessToken(SECRET, Instant.parse("2026-09-04T02:00:00Z")))));

        ClinicalSnapshotResult result = service().assemble(enabledWithPatient(PATIENT_ID));

        assertThat(result.outcome()).isEqualTo(ClinicalSnapshotOutcome.AUTHENTICATION_REQUIRED);
        assertThat(result.detail()).contains("expired");
        assertThat(result.toString()).doesNotContain(SECRET);
        verify(capabilityDiscovery, never()).discover(any());
        verify(assembler, never()).assemble(any(), any(), any(), any());
    }

    @Test
    void capabilityDiscoveryFailureIsUnavailableWithoutAssembly() {
        usableToken();
        when(capabilityDiscovery.discover(any())).thenThrow(new IllegalStateException("metadata down"));

        ClinicalSnapshotResult result = service().assemble(enabledWithPatient(PATIENT_ID));

        assertThat(result.outcome()).isEqualTo(ClinicalSnapshotOutcome.SNAPSHOT_UNAVAILABLE);
        assertThat(result.patientStatus()).isEqualTo(ClinicalSnapshotResourceStatus.FAILED);
        assertThat(result.toString()).doesNotContain("metadata down");
        verify(assembler, never()).assemble(any(), any(), any(), any());
    }

    @Test
    void discoversCapabilitiesOnceThenDelegatesToAssembler() {
        usableToken();
        FhirServerCapabilities capabilities = patientReadOnly();
        when(capabilityDiscovery.discover(any())).thenReturn(capabilities);
        ClinicalSnapshotResult assembled = ClinicalSnapshotResult.unavailable(
                "oracle-health-sandbox",
                Instant.parse("2026-09-04T03:00:00Z"),
                ClinicalSnapshotResourceStatus.UNAVAILABLE,
                "Patient context could not be established");
        when(assembler.assemble(any(), any(), eq(PATIENT_ID), eq(capabilities))).thenReturn(assembled);

        ClinicalSnapshotResult result = service().assemble(enabledWithPatient(PATIENT_ID));

        assertThat(result.outcome()).isEqualTo(ClinicalSnapshotOutcome.SNAPSHOT_UNAVAILABLE);
        assertThat(result.toString()).doesNotContain(SECRET);
        assertThat(result.toString()).doesNotContain(PATIENT_ID);
        verify(capabilityDiscovery).discover(any());
        verify(assembler).assemble(any(), any(), eq(PATIENT_ID), eq(capabilities));
    }

    private void usableToken() {
        when(authenticationService.issuedProviderIfPresent())
                .thenReturn(Optional.of(new IssuedAccessTokenProvider(
                        new AccessToken(SECRET, Instant.parse("2026-09-04T04:00:00Z")))));
    }

    private OracleSandboxClinicalSnapshotService service() {
        return new OracleSandboxClinicalSnapshotService(
                new OracleSandboxReadinessService(new OracleSandboxProfileValidator(), verifier),
                authenticationService,
                capabilityDiscovery,
                assembler,
                CLOCK);
    }

    private static OracleHealthIntegrationProfile enabledWithPatient(String patientId) {
        return OracleHealthIntegrationProfile.from(
                OracleHealthIntegrationProfileTest.oracleServer(true, OracleHealthIntegrationProfileTest.smartAuth()),
                new FhirServersProperties.VendorIntegrationSettings(
                        "SANDBOX", "STANDALONE", "PATIENT", "PUBLIC_PKCE", patientId));
    }

    private static FhirServerCapabilities patientReadOnly() {
        CapabilityStatement statement = new CapabilityStatement();
        statement.setFhirVersion(Enumerations.FHIRVersion._4_0_1);
        CapabilityStatement.CapabilityStatementRestResourceComponent patient = statement.addRest().addResource();
        patient.setType("Patient");
        patient.addInteraction().setCode(CapabilityStatement.TypeRestfulInteraction.READ);
        return new FhirCapabilityDiscoveryService().interpret("oracle-health-sandbox", statement);
    }
}

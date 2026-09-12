package lab.healthcare.fhir.vendor.epic;

import lab.healthcare.fhir.auth.AccessToken;
import lab.healthcare.fhir.auth.IssuedAccessTokenProvider;
import lab.healthcare.fhir.capability.FhirCapabilityDiscoveryService;
import lab.healthcare.fhir.capability.FhirServerCapabilities;
import lab.healthcare.fhir.projection.ClinicalProjectionAssembler;
import lab.healthcare.fhir.projection.ClinicalProjectionResult;
import lab.healthcare.fhir.server.FhirServersProperties;
import lab.healthcare.fhir.smart.SmartAuthorizationCoordinator;
import lab.healthcare.fhir.smart.SmartConfigurationClient;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotContents;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotOutcome;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotResourceStatus;

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
class EpicSandboxClinicalProjectionServiceTest {

    private static final Clock CLOCK = Clock.fixed(Instant.parse("2026-09-12T18:00:00Z"), ZoneOffset.UTC);
    private static final String SECRET = "epic-live-access-token";
    private static final String PATIENT_ID = "lab-configured-patient";

    @Mock
    private SmartConfigurationClient smartConfigurationClient;

    @Mock
    private SmartAuthorizationCoordinator coordinator;

    @Mock
    private EpicSandboxCapabilityDiscoveryService capabilityDiscovery;

    @Mock
    private ClinicalProjectionAssembler assembler;

    @Test
    void disabledProfileDoesNotCallEpic() {
        ClinicalProjectionResult result = service().assemble(EpicIntegrationProfileTest.completePublicPkce());

        assertThat(result.outcome()).isEqualTo(ClinicalSnapshotOutcome.AUTHENTICATION_REQUIRED);
        verify(coordinator, never()).lastIssuedProvider();
        verify(capabilityDiscovery, never()).discover(any());
        verify(assembler, never()).assemble(any(), any(), any(), any());
        verify(assembler, never()).assemble(any(), any(), any(), any(), any());
    }

    @Test
    void missingPatientIdIsContextNotConfiguredWithoutHttp() {
        ClinicalProjectionResult result = service().assemble(EpicIntegrationProfileTest.enabledCompletePublicPkce());

        assertThat(result.outcome()).isEqualTo(ClinicalSnapshotOutcome.PATIENT_CONTEXT_NOT_CONFIGURED);
        verify(capabilityDiscovery, never()).discover(any());
        verify(assembler, never()).assemble(any(), any(), any(), any(), any());
    }

    @Test
    void missingTokenIsAuthenticationRequiredWithoutHttp() {
        when(coordinator.lastIssuedProvider()).thenReturn(Optional.empty());

        ClinicalProjectionResult result = service().assemble(enabledWithPatient(PATIENT_ID));

        assertThat(result.outcome()).isEqualTo(ClinicalSnapshotOutcome.AUTHENTICATION_REQUIRED);
        assertThat(result.detail()).contains("No usable access token");
        verify(capabilityDiscovery, never()).discover(any());
        verify(assembler, never()).assemble(any(), any(), any(), any(), any());
    }

    @Test
    void expiredTokenIsAuthenticationRequiredWithoutHttp() {
        when(coordinator.lastIssuedProvider())
                .thenReturn(Optional.of(new IssuedAccessTokenProvider(
                        new AccessToken(SECRET, Instant.parse("2026-09-12T17:00:00Z")))));

        ClinicalProjectionResult result = service().assemble(enabledWithPatient(PATIENT_ID));

        assertThat(result.outcome()).isEqualTo(ClinicalSnapshotOutcome.AUTHENTICATION_REQUIRED);
        assertThat(result.detail()).contains("expired");
        assertThat(result.toString()).doesNotContain(SECRET);
        verify(capabilityDiscovery, never()).discover(any());
        verify(assembler, never()).assemble(any(), any(), any(), any(), any());
    }

    @Test
    void capabilityDiscoveryFailureIsUnavailableWithoutAssembly() {
        usableToken();
        when(capabilityDiscovery.discover(any())).thenThrow(new IllegalStateException("metadata down"));

        ClinicalProjectionResult result = service().assemble(enabledWithPatient(PATIENT_ID));

        assertThat(result.outcome()).isEqualTo(ClinicalSnapshotOutcome.SNAPSHOT_UNAVAILABLE);
        assertThat(result.patientStatus()).isEqualTo(ClinicalSnapshotResourceStatus.FAILED);
        assertThat(result.toString()).doesNotContain("metadata down");
        verify(assembler, never()).assemble(any(), any(), any(), any(), any());
    }

    @Test
    void discoversCapabilitiesOnceThenDelegatesWithoutMedicationRequests() {
        usableToken();
        FhirServerCapabilities capabilities = patientReadOnly();
        when(capabilityDiscovery.discover(any())).thenReturn(capabilities);
        ClinicalProjectionResult assembled = ClinicalProjectionResult.unavailable(
                EpicIntegrationProfile.SANDBOX_SERVER,
                Instant.parse("2026-09-12T18:00:00Z"),
                ClinicalSnapshotResourceStatus.UNAVAILABLE,
                "Patient context could not be established");
        when(assembler.assemble(
                        any(),
                        any(),
                        eq(PATIENT_ID),
                        eq(capabilities),
                        eq(ClinicalSnapshotContents.withoutMedicationRequests())))
                .thenReturn(assembled);

        ClinicalProjectionResult result = service().assemble(enabledWithPatient(PATIENT_ID));

        assertThat(result.outcome()).isEqualTo(ClinicalSnapshotOutcome.SNAPSHOT_UNAVAILABLE);
        assertThat(result.toString()).doesNotContain(SECRET);
        assertThat(result.toString()).doesNotContain(PATIENT_ID);
        verify(capabilityDiscovery).discover(any());
        verify(assembler)
                .assemble(
                        eq(EpicIntegrationProfile.SANDBOX_SERVER),
                        any(),
                        eq(PATIENT_ID),
                        eq(capabilities),
                        eq(ClinicalSnapshotContents.withoutMedicationRequests()));
        verify(assembler, never()).assemble(any(), any(), any(), any());
    }

    private void usableToken() {
        when(coordinator.lastIssuedProvider())
                .thenReturn(Optional.of(new IssuedAccessTokenProvider(
                        new AccessToken(SECRET, Instant.parse("2026-09-12T19:00:00Z")))));
    }

    private EpicSandboxClinicalProjectionService service() {
        return new EpicSandboxClinicalProjectionService(
                new EpicSandboxAuthenticationService(
                        new EpicProfileValidator(), smartConfigurationClient, coordinator),
                capabilityDiscovery,
                assembler,
                CLOCK);
    }

    private static EpicIntegrationProfile enabledWithPatient(String patientId) {
        return EpicIntegrationProfile.from(
                EpicIntegrationProfileTest.epicServer(true, EpicIntegrationProfileTest.smartAuth()),
                new FhirServersProperties.VendorIntegrationSettings(
                        "SANDBOX", "STANDALONE", "PATIENT", "PUBLIC_PKCE", patientId));
    }

    private static FhirServerCapabilities patientReadOnly() {
        CapabilityStatement statement = new CapabilityStatement();
        statement.setFhirVersion(Enumerations.FHIRVersion._4_0_1);
        CapabilityStatement.CapabilityStatementRestResourceComponent patient = statement.addRest().addResource();
        patient.setType("Patient");
        patient.addInteraction().setCode(CapabilityStatement.TypeRestfulInteraction.READ);
        return new FhirCapabilityDiscoveryService().interpret("epic-sandbox", statement);
    }
}

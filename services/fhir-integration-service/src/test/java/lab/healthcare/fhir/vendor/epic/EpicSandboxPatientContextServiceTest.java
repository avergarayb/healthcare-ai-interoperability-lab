package lab.healthcare.fhir.vendor.epic;

import lab.healthcare.fhir.auth.AccessToken;
import lab.healthcare.fhir.auth.IssuedAccessTokenProvider;
import lab.healthcare.fhir.capability.FhirCapabilityDiscoveryServiceTest;
import lab.healthcare.fhir.capability.FhirServerCapabilities;
import lab.healthcare.fhir.exception.FhirClientException;
import lab.healthcare.fhir.exception.FhirErrorCategory;
import lab.healthcare.fhir.exception.FhirErrorDetails;
import lab.healthcare.fhir.patient.PatientContextSource;
import lab.healthcare.fhir.routing.FhirPatientReadOutcome;
import lab.healthcare.fhir.routing.FhirPatientReadResult;
import lab.healthcare.fhir.routing.RoutingService;
import lab.healthcare.fhir.server.FhirServersProperties;
import lab.healthcare.fhir.smart.SmartAuthorizationCoordinator;
import lab.healthcare.fhir.smart.SmartConfigurationClient;

import ca.uhn.fhir.rest.server.exceptions.AuthenticationException;
import ca.uhn.fhir.rest.server.exceptions.ForbiddenOperationException;
import ca.uhn.fhir.rest.server.exceptions.ResourceNotFoundException;
import org.hl7.fhir.r4.model.CapabilityStatement;
import org.hl7.fhir.r4.model.Enumerations;
import org.hl7.fhir.r4.model.HumanName;
import org.hl7.fhir.r4.model.Patient;
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
class EpicSandboxPatientContextServiceTest {

    private static final Clock CLOCK = Clock.fixed(Instant.parse("2026-09-08T18:00:00Z"), ZoneOffset.UTC);
    private static final String SECRET = "epic-live-access-token";
    private static final String PATIENT_ID = "lab-configured-patient";

    @Mock
    private SmartConfigurationClient smartConfigurationClient;

    @Mock
    private SmartAuthorizationCoordinator coordinator;

    @Mock
    private EpicSandboxCapabilityDiscoveryService capabilityDiscovery;

    @Mock
    private RoutingService routingService;

    @Test
    void disabledProfileDoesNotCallEpic() {
        FhirPatientReadResult result = service().readPatient(EpicIntegrationProfileTest.completePublicPkce());

        assertThat(result.outcome()).isEqualTo(FhirPatientReadOutcome.AUTHENTICATION_REQUIRED);
        assertThat(result.toString()).doesNotContain(SECRET);
        verify(coordinator, never()).lastIssuedProvider();
        verify(capabilityDiscovery, never()).discover(any());
        verify(routingService, never()).readPatient(any(), any(), any());
    }

    @Test
    void missingPatientIdIsContextNotConfiguredWithoutHttp() {
        FhirPatientReadResult result =
                service().readPatient(EpicIntegrationProfileTest.enabledCompletePublicPkce());

        assertThat(result.outcome()).isEqualTo(FhirPatientReadOutcome.PATIENT_CONTEXT_NOT_CONFIGURED);
        assertThat(result.hasPatientContext()).isFalse();
        verify(capabilityDiscovery, never()).discover(any());
        verify(routingService, never()).readPatient(any(), any(), any());
    }

    @Test
    void blankPatientIdIsContextNotConfiguredWithoutHttp() {
        FhirPatientReadResult result = service().readPatient(enabledWithPatient("   "));

        assertThat(result.outcome()).isEqualTo(FhirPatientReadOutcome.PATIENT_CONTEXT_NOT_CONFIGURED);
        verify(routingService, never()).readPatient(any(), any(), any());
    }

    @Test
    void configuredContextUsesConfiguredSource() {
        assertThat(enabledWithPatient(PATIENT_ID).hasConfiguredPatientId()).isTrue();
        assertThat(lab.healthcare.fhir.patient.PatientContexts.configured(
                        EpicIntegrationProfile.SANDBOX_SERVER, PATIENT_ID)
                .orElseThrow()
                .source())
                .isEqualTo(PatientContextSource.CONFIGURED);
    }

    @Test
    void missingTokenIsAuthenticationRequiredWithoutHttp() {
        when(coordinator.lastIssuedProvider()).thenReturn(Optional.empty());

        FhirPatientReadResult result = service().readPatient(enabledWithPatient(PATIENT_ID));

        assertThat(result.outcome()).isEqualTo(FhirPatientReadOutcome.AUTHENTICATION_REQUIRED);
        assertThat(result.detail()).contains("No usable access token");
        verify(capabilityDiscovery, never()).discover(any());
        verify(routingService, never()).readPatient(any(), any(), any());
    }

    @Test
    void expiredTokenIsAuthenticationRequiredWithoutHttp() {
        when(coordinator.lastIssuedProvider())
                .thenReturn(Optional.of(new IssuedAccessTokenProvider(
                        new AccessToken(SECRET, Instant.parse("2026-09-08T17:00:00Z")))));

        FhirPatientReadResult result = service().readPatient(enabledWithPatient(PATIENT_ID));

        assertThat(result.outcome()).isEqualTo(FhirPatientReadOutcome.AUTHENTICATION_REQUIRED);
        assertThat(result.detail()).contains("expired");
        assertThat(result.toString()).doesNotContain(SECRET);
        verify(capabilityDiscovery, never()).discover(any());
        verify(routingService, never()).readPatient(any(), any(), any());
    }

    @Test
    void missingPatientReadCapabilityIsUnsupportedWithoutRead() {
        usableToken();
        when(capabilityDiscovery.discover(any())).thenReturn(observationOnly());

        FhirPatientReadResult result = service().readPatient(enabledWithPatient(PATIENT_ID));

        assertThat(result.outcome()).isEqualTo(FhirPatientReadOutcome.CAPABILITY_UNSUPPORTED);
        verify(routingService, never()).readPatient(any(), any(), any());
    }

    @Test
    void searchTypeWithoutReadIsUnsupportedWithoutRead() {
        usableToken();
        when(capabilityDiscovery.discover(any())).thenReturn(patientSearchOnly());

        FhirPatientReadResult result = service().readPatient(enabledWithPatient(PATIENT_ID));

        assertThat(result.outcome()).isEqualTo(FhirPatientReadOutcome.CAPABILITY_UNSUPPORTED);
        verify(routingService, never()).readPatient(any(), any(), any());
    }

    @Test
    void validTokenContextAndCapabilityExecuteGenericRead() {
        usableToken();
        when(capabilityDiscovery.discover(any()))
                .thenReturn(new lab.healthcare.fhir.capability.FhirCapabilityDiscoveryService()
                        .interpret("epic-sandbox", FhirCapabilityDiscoveryServiceTest.sampleStatement()));
        Patient patient = new Patient();
        patient.setId(PATIENT_ID);
        patient.addName(new HumanName().setFamily("SecretFamily"));
        when(routingService.readPatient(any(), any(), eq(PATIENT_ID))).thenReturn(patient);

        FhirPatientReadResult result = service().readPatient(enabledWithPatient(PATIENT_ID));

        assertThat(result.outcome()).isEqualTo(FhirPatientReadOutcome.PATIENT_READ_SUCCEEDED);
        assertThat(result.responseType()).isEqualTo("Patient");
        assertThat(result.hasPatientContext()).isTrue();
        assertThat(result.toString()).doesNotContain(SECRET);
        assertThat(result.toString()).doesNotContain(PATIENT_ID);
        assertThat(result.toString()).doesNotContain("SecretFamily");
        verify(routingService).readPatient(eq(EpicIntegrationProfile.SANDBOX_SERVER), any(), eq(PATIENT_ID));
        verify(routingService, never()).searchPatients(any(), any(), any());
    }

    @Test
    void http401IsAuthenticationRejected() {
        usableToken();
        when(capabilityDiscovery.discover(any()))
                .thenReturn(new lab.healthcare.fhir.capability.FhirCapabilityDiscoveryService()
                        .interpret("epic-sandbox", FhirCapabilityDiscoveryServiceTest.sampleStatement()));
        when(routingService.readPatient(any(), any(), any()))
                .thenThrow(FhirClientException.from(new AuthenticationException()));

        FhirPatientReadResult result = service().readPatient(enabledWithPatient(PATIENT_ID));

        assertThat(result.outcome()).isEqualTo(FhirPatientReadOutcome.AUTHENTICATION_REJECTED);
        assertThat(result.httpStatus()).isEqualTo(401);
        assertThat(result.toString()).doesNotContain(SECRET);
    }

    @Test
    void http403IsAuthorizationDenied() {
        usableToken();
        when(capabilityDiscovery.discover(any()))
                .thenReturn(new lab.healthcare.fhir.capability.FhirCapabilityDiscoveryService()
                        .interpret("epic-sandbox", FhirCapabilityDiscoveryServiceTest.sampleStatement()));
        when(routingService.readPatient(any(), any(), any()))
                .thenThrow(FhirClientException.from(new ForbiddenOperationException("forbidden")));

        FhirPatientReadResult result = service().readPatient(enabledWithPatient(PATIENT_ID));

        assertThat(result.outcome()).isEqualTo(FhirPatientReadOutcome.AUTHORIZATION_DENIED);
        assertThat(result.dependencyCategory()).isEqualTo(FhirErrorCategory.AUTHORIZATION_ERROR);
    }

    @Test
    void http404IsPatientNotFoundWithoutFallbackSearch() {
        usableToken();
        when(capabilityDiscovery.discover(any()))
                .thenReturn(new lab.healthcare.fhir.capability.FhirCapabilityDiscoveryService()
                        .interpret("epic-sandbox", FhirCapabilityDiscoveryServiceTest.sampleStatement()));
        when(routingService.readPatient(any(), any(), any()))
                .thenThrow(FhirClientException.from(new ResourceNotFoundException("Patient/" + PATIENT_ID)));

        FhirPatientReadResult result = service().readPatient(enabledWithPatient(PATIENT_ID));

        assertThat(result.outcome()).isEqualTo(FhirPatientReadOutcome.PATIENT_NOT_FOUND);
        assertThat(result.httpStatus()).isEqualTo(404);
        assertThat(result.toString()).doesNotContain(PATIENT_ID);
        verify(routingService, never()).searchPatients(any(), any(), any());
    }

    @Test
    void dependencyFailureMapsWithoutClinicalPayload() {
        usableToken();
        when(capabilityDiscovery.discover(any()))
                .thenReturn(new lab.healthcare.fhir.capability.FhirCapabilityDiscoveryService()
                        .interpret("epic-sandbox", FhirCapabilityDiscoveryServiceTest.sampleStatement()));
        when(routingService.readPatient(any(), any(), any()))
                .thenThrow(new FhirClientException(
                        FhirErrorDetails.of(FhirErrorCategory.CONNECTION_ERROR, null), null));

        FhirPatientReadResult result = service().readPatient(enabledWithPatient(PATIENT_ID));

        assertThat(result.outcome()).isEqualTo(FhirPatientReadOutcome.DEPENDENCY_FAILURE);
        assertThat(result.dependencyCategory()).isEqualTo(FhirErrorCategory.CONNECTION_ERROR);
        assertThat(result.toString()).doesNotContain(SECRET);
        assertThat(result.toString()).doesNotContain(PATIENT_ID);
    }

    private void usableToken() {
        when(coordinator.lastIssuedProvider())
                .thenReturn(Optional.of(new IssuedAccessTokenProvider(
                        new AccessToken(SECRET, Instant.parse("2026-09-08T19:00:00Z")))));
    }

    private EpicSandboxPatientContextService service() {
        return new EpicSandboxPatientContextService(
                new EpicSandboxAuthenticationService(
                        new EpicProfileValidator(), smartConfigurationClient, coordinator),
                capabilityDiscovery,
                routingService,
                CLOCK);
    }

    private static EpicIntegrationProfile enabledWithPatient(String patientId) {
        return EpicIntegrationProfile.from(
                EpicIntegrationProfileTest.epicServer(true, EpicIntegrationProfileTest.smartAuth()),
                new FhirServersProperties.VendorIntegrationSettings(
                        "SANDBOX", "STANDALONE", "PATIENT", "PUBLIC_PKCE", patientId));
    }

    private static FhirServerCapabilities observationOnly() {
        CapabilityStatement statement = new CapabilityStatement();
        statement.setFhirVersion(Enumerations.FHIRVersion._4_0_1);
        CapabilityStatement.CapabilityStatementRestResourceComponent observation =
                statement.addRest().addResource();
        observation.setType("Observation");
        observation.addInteraction().setCode(CapabilityStatement.TypeRestfulInteraction.READ);
        return new lab.healthcare.fhir.capability.FhirCapabilityDiscoveryService()
                .interpret("epic-sandbox", statement);
    }

    private static FhirServerCapabilities patientSearchOnly() {
        CapabilityStatement statement = new CapabilityStatement();
        statement.setFhirVersion(Enumerations.FHIRVersion._4_0_1);
        CapabilityStatement.CapabilityStatementRestResourceComponent patient = statement.addRest().addResource();
        patient.setType("Patient");
        patient.addInteraction().setCode(CapabilityStatement.TypeRestfulInteraction.SEARCHTYPE);
        return new lab.healthcare.fhir.capability.FhirCapabilityDiscoveryService()
                .interpret("epic-sandbox", statement);
    }
}

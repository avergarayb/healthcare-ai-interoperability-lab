package lab.healthcare.fhir.vendor.epic;

import lab.healthcare.fhir.auth.AccessToken;
import lab.healthcare.fhir.auth.IssuedAccessTokenProvider;
import lab.healthcare.fhir.capability.FhirServerCapabilities;
import lab.healthcare.fhir.exception.FhirClientException;
import lab.healthcare.fhir.exception.FhirErrorCategory;
import lab.healthcare.fhir.exception.FhirErrorDetails;
import lab.healthcare.fhir.patient.PatientContextSource;
import lab.healthcare.fhir.routing.FhirObservationSearchOutcome;
import lab.healthcare.fhir.routing.FhirObservationSearchResult;
import lab.healthcare.fhir.routing.RoutingService;
import lab.healthcare.fhir.server.FhirServersProperties;
import lab.healthcare.fhir.smart.SmartAuthorizationCoordinator;
import lab.healthcare.fhir.smart.SmartConfigurationClient;

import ca.uhn.fhir.rest.server.exceptions.AuthenticationException;
import ca.uhn.fhir.rest.server.exceptions.ForbiddenOperationException;
import org.hl7.fhir.r4.model.Bundle;
import org.hl7.fhir.r4.model.CapabilityStatement;
import org.hl7.fhir.r4.model.Enumerations;
import org.hl7.fhir.r4.model.Observation;
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
class EpicSandboxObservationSearchServiceTest {

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
        FhirObservationSearchResult result =
                service().searchObservations(EpicIntegrationProfileTest.completePublicPkce());

        assertThat(result.outcome()).isEqualTo(FhirObservationSearchOutcome.AUTHENTICATION_REQUIRED);
        assertThat(result.toString()).doesNotContain(SECRET);
        verify(coordinator, never()).lastIssuedProvider();
        verify(capabilityDiscovery, never()).discover(any());
        verify(routingService, never()).searchObservations(any(), any(), any());
    }

    @Test
    void missingPatientIdIsContextNotConfiguredWithoutHttp() {
        FhirObservationSearchResult result =
                service().searchObservations(EpicIntegrationProfileTest.enabledCompletePublicPkce());

        assertThat(result.outcome()).isEqualTo(FhirObservationSearchOutcome.PATIENT_CONTEXT_NOT_CONFIGURED);
        assertThat(result.hasPatientContext()).isFalse();
        verify(capabilityDiscovery, never()).discover(any());
        verify(routingService, never()).searchObservations(any(), any(), any());
    }

    @Test
    void blankPatientIdIsContextNotConfiguredWithoutHttp() {
        FhirObservationSearchResult result = service().searchObservations(enabledWithPatient("   "));

        assertThat(result.outcome()).isEqualTo(FhirObservationSearchOutcome.PATIENT_CONTEXT_NOT_CONFIGURED);
        verify(routingService, never()).searchObservations(any(), any(), any());
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

        FhirObservationSearchResult result = service().searchObservations(enabledWithPatient(PATIENT_ID));

        assertThat(result.outcome()).isEqualTo(FhirObservationSearchOutcome.AUTHENTICATION_REQUIRED);
        assertThat(result.detail()).contains("No usable access token");
        verify(capabilityDiscovery, never()).discover(any());
        verify(routingService, never()).searchObservations(any(), any(), any());
    }

    @Test
    void expiredTokenIsAuthenticationRequiredWithoutHttp() {
        when(coordinator.lastIssuedProvider())
                .thenReturn(Optional.of(new IssuedAccessTokenProvider(
                        new AccessToken(SECRET, Instant.parse("2026-09-08T17:00:00Z")))));

        FhirObservationSearchResult result = service().searchObservations(enabledWithPatient(PATIENT_ID));

        assertThat(result.outcome()).isEqualTo(FhirObservationSearchOutcome.AUTHENTICATION_REQUIRED);
        assertThat(result.detail()).contains("expired");
        assertThat(result.toString()).doesNotContain(SECRET);
        verify(capabilityDiscovery, never()).discover(any());
        verify(routingService, never()).searchObservations(any(), any(), any());
    }

    @Test
    void missingObservationCapabilityIsUnsupportedWithoutSearch() {
        usableToken();
        when(capabilityDiscovery.discover(any())).thenReturn(patientReadOnly());

        FhirObservationSearchResult result = service().searchObservations(enabledWithPatient(PATIENT_ID));

        assertThat(result.outcome()).isEqualTo(FhirObservationSearchOutcome.CAPABILITY_UNSUPPORTED);
        verify(routingService, never()).searchObservations(any(), any(), any());
    }

    @Test
    void validTokenContextAndCapabilityExecuteGenericSearch() {
        usableToken();
        when(capabilityDiscovery.discover(any())).thenReturn(observationSearchSupported());
        Bundle bundle = new Bundle();
        bundle.setType(Bundle.BundleType.SEARCHSET);
        Observation observation = new Observation();
        observation.setId("secret-observation");
        bundle.addEntry().setResource(observation);
        when(routingService.searchObservations(any(), any(), eq(PATIENT_ID))).thenReturn(bundle);

        FhirObservationSearchResult result = service().searchObservations(enabledWithPatient(PATIENT_ID));

        assertThat(result.outcome()).isEqualTo(FhirObservationSearchOutcome.OBSERVATION_SEARCH_SUCCEEDED);
        assertThat(result.responseType()).isEqualTo("Bundle");
        assertThat(result.hasEntries()).isTrue();
        assertThat(result.toString()).doesNotContain(SECRET);
        assertThat(result.toString()).doesNotContain(PATIENT_ID);
        assertThat(result.toString()).doesNotContain("secret-observation");
        verify(routingService).searchObservations(eq(EpicIntegrationProfile.SANDBOX_SERVER), any(), eq(PATIENT_ID));
        verify(routingService, never()).searchPatients(any(), any(), any());
        verify(routingService, never()).readPatient(any(), any(), any());
        verify(routingService, never()).searchConditions(any(), any(), any());
    }

    @Test
    void emptyBundleIsSuccessWithoutEntries() {
        usableToken();
        when(capabilityDiscovery.discover(any())).thenReturn(observationSearchSupported());
        Bundle bundle = new Bundle();
        bundle.setType(Bundle.BundleType.SEARCHSET);
        when(routingService.searchObservations(any(), any(), eq(PATIENT_ID))).thenReturn(bundle);

        FhirObservationSearchResult result = service().searchObservations(enabledWithPatient(PATIENT_ID));

        assertThat(result.outcome()).isEqualTo(FhirObservationSearchOutcome.OBSERVATION_SEARCH_SUCCEEDED);
        assertThat(result.hasEntries()).isFalse();
        assertThat(result.toString()).doesNotContain("EMPTY");
    }

    @Test
    void http401IsAuthenticationRejected() {
        usableToken();
        when(capabilityDiscovery.discover(any())).thenReturn(observationSearchSupported());
        when(routingService.searchObservations(any(), any(), any()))
                .thenThrow(FhirClientException.from(new AuthenticationException()));

        FhirObservationSearchResult result = service().searchObservations(enabledWithPatient(PATIENT_ID));

        assertThat(result.outcome()).isEqualTo(FhirObservationSearchOutcome.AUTHENTICATION_REJECTED);
        assertThat(result.httpStatus()).isEqualTo(401);
        assertThat(result.toString()).doesNotContain(SECRET);
    }

    @Test
    void http403IsAuthorizationDenied() {
        usableToken();
        when(capabilityDiscovery.discover(any())).thenReturn(observationSearchSupported());
        when(routingService.searchObservations(any(), any(), any()))
                .thenThrow(FhirClientException.from(new ForbiddenOperationException("forbidden")));

        FhirObservationSearchResult result = service().searchObservations(enabledWithPatient(PATIENT_ID));

        assertThat(result.outcome()).isEqualTo(FhirObservationSearchOutcome.AUTHORIZATION_DENIED);
        assertThat(result.dependencyCategory()).isEqualTo(FhirErrorCategory.AUTHORIZATION_ERROR);
    }

    @Test
    void dependencyFailureMapsWithoutClinicalPayload() {
        usableToken();
        when(capabilityDiscovery.discover(any())).thenReturn(observationSearchSupported());
        when(routingService.searchObservations(any(), any(), any()))
                .thenThrow(new FhirClientException(
                        FhirErrorDetails.of(FhirErrorCategory.CONNECTION_ERROR, null), null));

        FhirObservationSearchResult result = service().searchObservations(enabledWithPatient(PATIENT_ID));

        assertThat(result.outcome()).isEqualTo(FhirObservationSearchOutcome.DEPENDENCY_FAILURE);
        assertThat(result.dependencyCategory()).isEqualTo(FhirErrorCategory.CONNECTION_ERROR);
        assertThat(result.toString()).doesNotContain(SECRET);
        assertThat(result.toString()).doesNotContain(PATIENT_ID);
    }

    private void usableToken() {
        when(coordinator.lastIssuedProvider())
                .thenReturn(Optional.of(new IssuedAccessTokenProvider(
                        new AccessToken(SECRET, Instant.parse("2026-09-08T19:00:00Z")))));
    }

    private EpicSandboxObservationSearchService service() {
        return new EpicSandboxObservationSearchService(
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

    private static FhirServerCapabilities patientReadOnly() {
        CapabilityStatement statement = new CapabilityStatement();
        statement.setFhirVersion(Enumerations.FHIRVersion._4_0_1);
        CapabilityStatement.CapabilityStatementRestResourceComponent patient = statement.addRest().addResource();
        patient.setType("Patient");
        patient.addInteraction().setCode(CapabilityStatement.TypeRestfulInteraction.READ);
        return new lab.healthcare.fhir.capability.FhirCapabilityDiscoveryService()
                .interpret("epic-sandbox", statement);
    }

    private static FhirServerCapabilities observationSearchSupported() {
        CapabilityStatement statement = new CapabilityStatement();
        statement.setFhirVersion(Enumerations.FHIRVersion._4_0_1);
        CapabilityStatement.CapabilityStatementRestResourceComponent observation = statement.addRest().addResource();
        observation.setType("Observation");
        observation.addInteraction().setCode(CapabilityStatement.TypeRestfulInteraction.SEARCHTYPE);
        return new lab.healthcare.fhir.capability.FhirCapabilityDiscoveryService()
                .interpret("epic-sandbox", statement);
    }
}

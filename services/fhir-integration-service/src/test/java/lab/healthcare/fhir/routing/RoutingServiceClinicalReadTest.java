package lab.healthcare.fhir.routing;

import lab.healthcare.fhir.auth.oauth2.OAuth2TokenClient;
import lab.healthcare.fhir.client.FhirAccessTokenProviders;
import lab.healthcare.fhir.client.FhirClientFactory;
import lab.healthcare.fhir.observability.FhirAuditOperation;
import lab.healthcare.fhir.observability.FhirAuditOutcome;
import lab.healthcare.fhir.observability.InMemoryFhirMetricsRecorder;
import lab.healthcare.fhir.observability.LoggingFhirAuditRecorder;
import lab.healthcare.fhir.resilience.FhirCircuitBreakerRegistry;
import lab.healthcare.fhir.resilience.FhirRetryExecutor;
import lab.healthcare.fhir.resilience.bulkhead.FhirBulkheadRegistry;
import lab.healthcare.fhir.resilience.ratelimit.FhirRateLimiterRegistry;
import lab.healthcare.fhir.server.FhirServerProfile;
import lab.healthcare.fhir.server.FhirServerProfileRegistry;
import lab.healthcare.fhir.server.FhirServersProperties;
import lab.healthcare.fhir.smart.AuthorizationCodeClient;
import lab.healthcare.fhir.smart.SmartConfigurationClient;

import ca.uhn.fhir.context.FhirContext;
import ca.uhn.fhir.rest.client.api.IGenericClient;
import ca.uhn.fhir.rest.gclient.ICriterion;
import org.hl7.fhir.r4.model.Appointment;
import org.hl7.fhir.r4.model.Bundle;
import org.hl7.fhir.r4.model.Encounter;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Answers;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.Clock;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class RoutingServiceClinicalReadTest {

    private final LoggingFhirAuditRecorder auditRecorder = new LoggingFhirAuditRecorder();
    private final InMemoryFhirMetricsRecorder metricsRecorder = new InMemoryFhirMetricsRecorder();

    @Mock
    private FhirClientFactory mockFactory;

    @Mock(answer = Answers.RETURNS_DEEP_STUBS)
    private IGenericClient fhirClient;

    @Test
    void encounterSearchReusesDestinationClientAndOmitsClinicalTextFromAudit() {
        Bundle bundle = new Bundle();
        bundle.setType(Bundle.BundleType.SEARCHSET);
        when(mockFactory.createContext(any(FhirServerProfile.class))).thenReturn(FhirContext.forR4());
        when(mockFactory.createClient(any(FhirContext.class), any(FhirServerProfile.class), any())).thenReturn(fhirClient);
        when(fhirClient.search()
                        .forResource(eq(Encounter.class))
                        .where(any(ICriterion.class))
                        .and(any(ICriterion.class))
                        .count(25)
                        .returnBundle(eq(Bundle.class))
                        .execute())
                .thenReturn(bundle);
        RoutingService routing = routing(mockFactory);

        Bundle actual = routing.searchEncountersByPatientAndStatus("local-hapi", "pat-1", "finished", 25);

        assertThat(actual.getType()).isEqualTo(Bundle.BundleType.SEARCHSET);
        assertThat(auditRecorder.recorded()).hasSize(1);
        assertThat(auditRecorder.recorded().getFirst().outcome()).isEqualTo(FhirAuditOutcome.SUCCESS);
        assertThat(auditRecorder.recorded().getFirst().context().operation())
                .isEqualTo(FhirAuditOperation.ENCOUNTER_SEARCH);
        assertThat(auditRecorder.recorded().getFirst().toLogLine()).doesNotContain("finished");
        assertThat(auditRecorder.recorded().getFirst().toLogLine()).doesNotContain("pat-1");
        assertThat(metricsRecorder.snapshot().operationsByType())
                .containsEntry(FhirAuditOperation.ENCOUNTER_SEARCH.name(), 1L);
    }

    @Test
    void appointmentReadReusesDestinationClient() {
        Appointment appointment = new Appointment();
        appointment.setId("appt-1");
        appointment.setDescription("synthetic pressure note");
        when(mockFactory.createContext(any(FhirServerProfile.class))).thenReturn(FhirContext.forR4());
        when(mockFactory.createClient(any(FhirContext.class), any(FhirServerProfile.class), any())).thenReturn(fhirClient);
        when(fhirClient.read().resource(eq(Appointment.class)).withId("appt-1").execute()).thenReturn(appointment);
        RoutingService routing = routing(mockFactory);

        Appointment actual = routing.readAppointment("local-hapi", "appt-1");

        assertThat(actual.getIdElement().getIdPart()).isEqualTo("appt-1");
        assertThat(auditRecorder.recorded()).hasSize(1);
        assertThat(auditRecorder.recorded().getFirst().context().operation()).isEqualTo(FhirAuditOperation.READ);
        assertThat(auditRecorder.recorded().getFirst().context().resourceType()).isEqualTo("Appointment");
        assertThat(auditRecorder.recorded().getFirst().toLogLine()).doesNotContain("synthetic pressure note");
    }

    private RoutingService routing(FhirClientFactory factory) {
        return new RoutingService(
                new FhirServerProfileRegistry(twoServers()),
                factory,
                new FhirAccessTokenProviders(
                        new OAuth2TokenClient(),
                        new SmartConfigurationClient(),
                        new AuthorizationCodeClient(),
                        Clock.systemUTC()),
                auditRecorder,
                metricsRecorder,
                FhirRetryExecutor.immediate(),
                new FhirCircuitBreakerRegistry(),
                new FhirRateLimiterRegistry(),
                new FhirBulkheadRegistry());
    }

    private static FhirServersProperties twoServers() {
        return new FhirServersProperties(
                "local-hapi",
                Map.of(
                        "local-hapi",
                        FhirServersProperties.ServerSettings.of("http://localhost:8080/fhir", "R4", true, null),
                        "example-org",
                        FhirServersProperties.ServerSettings.of("https://example.org/fhir", "R4", false, null)));
    }
}

package lab.healthcare.fhir.clinicalread;

import lab.healthcare.fhir.exception.FhirClientException;
import lab.healthcare.fhir.exception.FhirErrorCategory;
import lab.healthcare.fhir.exception.FhirErrorDetails;
import lab.healthcare.fhir.routing.RoutingService;
import lab.healthcare.fhir.server.FhirServersProperties;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.hl7.fhir.r4.model.Appointment;
import org.hl7.fhir.r4.model.Bundle;
import org.hl7.fhir.r4.model.Encounter;
import org.hl7.fhir.r4.model.Observation;
import org.hl7.fhir.r4.model.Patient;
import org.hl7.fhir.r4.model.Reference;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.Instant;
import java.util.Date;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class ClinicalReadServiceTest {

    @Mock
    private RoutingService routing;

    @Test
    void readsPreserveIdentifierAndReferences() {
        ClinicalReadService service = service("local-hapi");
        Patient patient = new Patient();
        patient.setId("pat-1");
        patient.addIdentifier().setSystem("https://lab.local/followup-case").setValue("CASE-1");
        patient.addName().setFamily("Quispe").addGiven("Ana");
        when(routing.readPatientByLogicalId("local-hapi", "pat-1")).thenReturn(patient);

        Observation observation = new Observation();
        observation.setId("obs-1");
        observation.setStatus(Observation.ObservationStatus.FINAL);
        observation.setSubject(new Reference("Patient/pat-1"));
        observation.setEncounter(new Reference("Encounter/enc-1"));
        Bundle observations = bundle(observation, null);
        when(routing.searchObservationsByPatientAndStatus("local-hapi", "pat-1", "final", ClinicalReadLimits.PAGE_SIZE))
                .thenReturn(observations);

        Appointment appointment = new Appointment();
        appointment.setId("appt-1");
        appointment.setStatus(Appointment.AppointmentStatus.BOOKED);
        appointment.setStart(Date.from(Instant.parse("2026-09-01T15:00:00Z")));
        appointment.addParticipant().getActor().setReference("Patient/pat-1");
        when(routing.searchAppointmentsByPatient("local-hapi", "pat-1", ClinicalReadLimits.PAGE_SIZE))
                .thenReturn(bundle(appointment, null));

        JsonNode read = service.readPatient("pat-1");
        assertThat(read.get("contractVersion").asText()).isEqualTo("clinical-read-v1");
        assertThat(read.get("resource").get("id").asText()).isEqualTo("pat-1");
        assertThat(read.get("resource").get("identifier").get(0).get("system").asText())
                .isEqualTo("https://lab.local/followup-case");
        assertThat(read.get("resource").get("identifier").get(0).get("value").asText()).isEqualTo("CASE-1");
        assertThat(read.get("resource").get("name").get(0).get("family").asText()).isEqualTo("Quispe");

        JsonNode found = service.searchObservations("pat-1", "final");
        assertThat(found.get("collectionStatus").asText()).isEqualTo("complete");
        assertThat(found.get("resources").get(0).get("subject").get("reference").asText()).isEqualTo("Patient/pat-1");
        assertThat(found.get("resources").get(0).get("encounter").get("reference").asText())
                .isEqualTo("Encounter/enc-1");

        JsonNode appointments = service.searchAppointments("pat-1");
        assertThat(appointments.get("resources").get(0).get("id").asText()).isEqualTo("appt-1");
        assertThat(appointments.get("resources").get(0).get("status").asText()).isEqualTo("booked");
        assertThat(appointments.get("resources").get(0).get("participant").get(0).get("actor").get("reference").asText())
                .isEqualTo("Patient/pat-1");
    }

    @Test
    void absenceIsNotConnectivityFailure() {
        ClinicalReadService service = service("local-hapi");
        when(routing.readEncounter("local-hapi", "enc-missing"))
                .thenThrow(notFound());
        when(routing.searchPatientsByIdentifier(
                        "local-hapi", "https://lab.example/mrn", "CASE-1", ClinicalReadLimits.PAGE_SIZE))
                .thenThrow(notFound());
        when(routing.readAppointment("local-hapi", "appt-down"))
                .thenThrow(new FhirClientException(FhirErrorDetails.of(FhirErrorCategory.CONNECTION_ERROR, null), null));

        assertThatThrownBy(() -> service.readEncounter("enc-missing"))
                .isInstanceOf(ClinicalReadException.class)
                .extracting(ex -> ((ClinicalReadException) ex).code())
                .isEqualTo("not_found");
        assertThatThrownBy(() -> service.searchPatients("https://lab.example/mrn", "CASE-1"))
                .extracting(ex -> ((ClinicalReadException) ex).code())
                .isEqualTo("unavailable");
        assertThatThrownBy(() -> service.readAppointment("appt-down"))
                .extracting(ex -> ((ClinicalReadException) ex).code())
                .isEqualTo("unavailable");
    }

    @Test
    void boundedPagesStayIncompleteAndAFailedNextPageIsUnavailable() {
        ClinicalReadService service = service("local-hapi");
        when(routing.searchEncountersByPatientAndStatus(
                        "local-hapi", "pat-1", "finished", ClinicalReadLimits.PAGE_SIZE))
                .thenReturn(encounterPage("enc-1", "http://pages/2"));
        when(routing.loadNextSearchPage(eq("local-hapi"), eq("Encounter"), any(Bundle.class)))
                .thenReturn(
                        encounterPage("enc-2", "http://pages/3"),
                        encounterPage("enc-3", "http://pages/4"),
                        encounterPage("enc-4", "http://pages/5"));

        JsonNode page = service.searchEncounters("pat-1", "finished");

        assertThat(page.get("collectionStatus").asText()).isEqualTo("incomplete");
        assertThat(page.get("resources")).hasSize(4);
        assertThat(page.get("resources").get(3).get("id").asText()).isEqualTo("enc-4");
        verify(routing, times(3)).loadNextSearchPage(eq("local-hapi"), eq("Encounter"), any(Bundle.class));

        when(routing.searchEncountersByPatientAndStatus(
                        "local-hapi", "pat-2", "finished", ClinicalReadLimits.PAGE_SIZE))
                .thenReturn(encounterPage("enc-9", "http://pages/next"));
        when(routing.loadNextSearchPage(eq("local-hapi"), eq("Encounter"), any(Bundle.class)))
                .thenThrow(new FhirClientException(FhirErrorDetails.of(FhirErrorCategory.TIMEOUT, 408), null));
        assertThatThrownBy(() -> service.searchEncounters("pat-2", "finished"))
                .extracting(ex -> ((ClinicalReadException) ex).code())
                .isEqualTo("unavailable");
    }

    @Test
    void otherDestinationsAreRejectedBeforeRouting() {
        ClinicalReadService service = service("epic-sandbox");

        assertThatThrownBy(() -> service.readPatient("pat-1"))
                .extracting(ex -> ((ClinicalReadException) ex).code())
                .isEqualTo("destination_not_supported");
        verify(routing, never()).readPatientByLogicalId(any(), any());
        verify(routing, never()).searchPatientsByIdentifier(any(), any(), any(), anyInt());
    }

    private ClinicalReadService service(String activeServer, RoutingService routing) {
        return new ClinicalReadService(routing, new FhirServersProperties(activeServer, Map.of()), new ObjectMapper());
    }

    private ClinicalReadService service(String activeServer) {
        return service(activeServer, routing);
    }

    private static Bundle encounterPage(String id, String next) {
        Encounter encounter = new Encounter();
        encounter.setId(id);
        encounter.setStatus(Encounter.EncounterStatus.FINISHED);
        encounter.setSubject(new Reference("Patient/pat-1"));
        return bundle(encounter, next);
    }

    private static Bundle bundle(org.hl7.fhir.r4.model.Resource resource, String next) {
        Bundle bundle = new Bundle();
        bundle.setType(Bundle.BundleType.SEARCHSET);
        bundle.addEntry().setResource(resource);
        if (next != null) {
            bundle.addLink().setRelation(Bundle.LINK_NEXT).setUrl(next);
        }
        return bundle;
    }

    private static FhirClientException notFound() {
        return new FhirClientException(FhirErrorDetails.of(FhirErrorCategory.NOT_FOUND, 404), null);
    }
}

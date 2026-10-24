package lab.healthcare.fhir.clinicalread.web;

import lab.healthcare.fhir.clinicalread.ClinicalReadService;
import lab.healthcare.fhir.exception.FhirClientException;
import lab.healthcare.fhir.exception.FhirErrorCategory;
import lab.healthcare.fhir.exception.FhirErrorDetails;
import lab.healthcare.fhir.modelboundary.ModelBoundaryServiceTokenSettings;
import lab.healthcare.fhir.routing.RoutingService;
import lab.healthcare.fhir.server.FhirServersProperties;

import org.hl7.fhir.r4.model.Encounter;
import org.hl7.fhir.r4.model.Patient;
import org.hl7.fhir.r4.model.Reference;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import java.util.Map;

import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(ClinicalReadController.class)
@Import({
    ClinicalReadController.class,
    ClinicalReadService.class,
    ClinicalReadAuthConfiguration.class,
    ModelBoundaryServiceTokenSettings.class,
    ClinicalReadControllerTest.LocalHapi.class
})
@TestPropertySource(properties = "MODEL_BOUNDARY_SERVICE_TOKEN=" + ModelBoundaryServiceTokenSettings.TEST_DUMMY)
class ClinicalReadControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private RoutingService routing;

    @Test
    void missingTokenIs401AndDoesNotRead() throws Exception {
        mockMvc.perform(get("/api/clinical-read/v1/patients/pat-1"))
                .andExpect(status().isUnauthorized())
                .andExpect(content().string(""));
        verify(routing, never()).readPatientByLogicalId(org.mockito.ArgumentMatchers.any(), org.mockito.ArgumentMatchers.any());
    }

    @Test
    void wrongTokenIs401() throws Exception {
        mockMvc.perform(get("/api/clinical-read/v1/encounters")
                        .param("patient", "pat-1")
                        .param("status", "finished")
                        .header(ModelBoundaryServiceTokenSettings.HEADER, "invalid-token"))
                .andExpect(status().isUnauthorized())
                .andExpect(content().string(""));
        verify(routing, never()).searchEncountersByPatientAndStatus(
                org.mockito.ArgumentMatchers.any(),
                org.mockito.ArgumentMatchers.any(),
                org.mockito.ArgumentMatchers.any(),
                org.mockito.ArgumentMatchers.anyInt());
    }

    @Test
    void whitespaceWrappedAndDuplicateTokensAre401WithoutRead() throws Exception {
        mockMvc.perform(get("/api/clinical-read/v1/patients/pat-1")
                        .header(ModelBoundaryServiceTokenSettings.HEADER,
                                " " + ModelBoundaryServiceTokenSettings.TEST_DUMMY + " "))
                .andExpect(status().isUnauthorized())
                .andExpect(content().string(""));
        mockMvc.perform(get("/api/clinical-read/v1/patients/pat-1")
                        .header(ModelBoundaryServiceTokenSettings.HEADER,
                                ModelBoundaryServiceTokenSettings.TEST_DUMMY,
                                ModelBoundaryServiceTokenSettings.TEST_DUMMY))
                .andExpect(status().isUnauthorized())
                .andExpect(content().string(""));
        mockMvc.perform(get("/api/clinical-read/v1/patients/pat-1")
                        .header(ModelBoundaryServiceTokenSettings.HEADER, "tökén-inválido"))
                .andExpect(status().isUnauthorized())
                .andExpect(content().string(""));
        verify(routing, never()).readPatientByLogicalId(
                org.mockito.ArgumentMatchers.any(), org.mockito.ArgumentMatchers.any());
    }

    @Test
    void readAndSearchKeepFhirIdentifiers() throws Exception {
        Patient patient = new Patient();
        patient.setId("pat-1");
        patient.addIdentifier().setSystem("https://lab.local/followup-case").setValue("CASE-1");
        when(routing.readPatientByLogicalId("local-hapi", "pat-1")).thenReturn(patient);

        Encounter encounter = new Encounter();
        encounter.setId("enc-1");
        encounter.setStatus(Encounter.EncounterStatus.FINISHED);
        encounter.setSubject(new Reference("Patient/pat-1"));
        org.hl7.fhir.r4.model.Bundle bundle = new org.hl7.fhir.r4.model.Bundle();
        bundle.setType(org.hl7.fhir.r4.model.Bundle.BundleType.SEARCHSET);
        bundle.addEntry().setResource(encounter);
        when(routing.searchEncountersByPatientAndStatus("local-hapi", "pat-1", "finished", 25)).thenReturn(bundle);

        mockMvc.perform(get("/api/clinical-read/v1/patients/pat-1")
                        .header(ModelBoundaryServiceTokenSettings.HEADER, ModelBoundaryServiceTokenSettings.TEST_DUMMY))
                .andExpect(status().isOk())
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_JSON))
                .andExpect(jsonPath("$.contractVersion").value("clinical-read-v1"))
                .andExpect(jsonPath("$.destination").value("local-hapi"))
                .andExpect(jsonPath("$.resource.resourceType").value("Patient"))
                .andExpect(jsonPath("$.resource.id").value("pat-1"))
                .andExpect(jsonPath("$.resource.identifier[0].system").value("https://lab.local/followup-case"))
                .andExpect(jsonPath("$.resource.identifier[0].value").value("CASE-1"));

        mockMvc.perform(get("/api/clinical-read/v1/encounters")
                        .param("patient", "pat-1")
                        .param("status", "finished")
                        .header(ModelBoundaryServiceTokenSettings.HEADER, ModelBoundaryServiceTokenSettings.TEST_DUMMY))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.collectionStatus").value("complete"))
                .andExpect(jsonPath("$.resourceType").value("Encounter"))
                .andExpect(jsonPath("$.resources[0].id").value("enc-1"))
                .andExpect(jsonPath("$.resources[0].subject.reference").value("Patient/pat-1"));
    }

    @Test
    void missingResourceAndConnectivityUseDifferentErrors() throws Exception {
        when(routing.readObservationByLogicalId("local-hapi", "obs-missing"))
                .thenThrow(new FhirClientException(FhirErrorDetails.of(FhirErrorCategory.NOT_FOUND, 404), null));
        when(routing.readAppointment("local-hapi", "appt-down"))
                .thenThrow(new FhirClientException(FhirErrorDetails.of(FhirErrorCategory.CONNECTION_ERROR, null), null));

        mockMvc.perform(get("/api/clinical-read/v1/observations/obs-missing")
                        .header(ModelBoundaryServiceTokenSettings.HEADER, ModelBoundaryServiceTokenSettings.TEST_DUMMY))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.error").value("not_found"))
                .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("obs-missing"))));

        mockMvc.perform(get("/api/clinical-read/v1/appointments/appt-down")
                        .header(ModelBoundaryServiceTokenSettings.HEADER, ModelBoundaryServiceTokenSettings.TEST_DUMMY))
                .andExpect(status().isServiceUnavailable())
                .andExpect(jsonPath("$.error").value("unavailable"))
                .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("appt-down"))));
    }

    @Configuration
    static class LocalHapi {
        @Bean
        FhirServersProperties fhirServersProperties() {
            return new FhirServersProperties("local-hapi", Map.of());
        }
    }
}

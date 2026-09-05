package lab.healthcare.fhir.modelboundary.web;

import lab.healthcare.fhir.modelboundary.BoundaryCollection;
import lab.healthcare.fhir.modelboundary.BoundaryCondition;
import lab.healthcare.fhir.modelboundary.BoundaryPatient;
import lab.healthcare.fhir.modelboundary.ModelBoundaryContract;
import lab.healthcare.fhir.modelboundary.ModelBoundaryContractProvider;
import lab.healthcare.fhir.modelboundary.ModelBoundaryContractVersion;
import lab.healthcare.fhir.patient.PatientContextSource;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotOutcome;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotResourceStatus;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import java.time.Instant;
import java.util.List;

import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(ModelBoundaryContractController.class)
class ModelBoundaryContractControllerTest {

    private static final String PATIENT_ID = "secret-patient-12724067";

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private ModelBoundaryContractProvider provider;

    @Test
    void authenticationRequiredIs401JsonWithoutInventingRecords() throws Exception {
        when(provider.currentContract())
                .thenReturn(new ModelBoundaryContract(
                        ModelBoundaryContractVersion.V1,
                        "oracle-health-sandbox",
                        null,
                        null,
                        ClinicalSnapshotOutcome.AUTHENTICATION_REQUIRED,
                        null,
                        null,
                        null,
                        null,
                        null));

        mockMvc.perform(get("/api/model-boundary/v1"))
                .andExpect(status().isUnauthorized())
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_JSON))
                .andExpect(jsonPath("$.contractVersion").value("v1"))
                .andExpect(jsonPath("$.outcome").value("AUTHENTICATION_REQUIRED"))
                .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString(PATIENT_ID))))
                .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("access_token"))));
    }

    @Test
    void completeReturnsExactV1ContractIncludingRecords() throws Exception {
        when(provider.currentContract()).thenReturn(completeContract());

        mockMvc.perform(get("/api/model-boundary/v1"))
                .andExpect(status().isOk())
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_JSON))
                .andExpect(jsonPath("$.contractVersion").value("v1"))
                .andExpect(jsonPath("$.outcome").value("SNAPSHOT_COMPLETE"))
                .andExpect(jsonPath("$.destination").value("oracle-health-sandbox"))
                .andExpect(jsonPath("$.contextSource").value("CONFIGURED"))
                .andExpect(jsonPath("$.patient.status").value("SUCCESS"))
                .andExpect(jsonPath("$.patient.resourceType").value("Patient"))
                .andExpect(jsonPath("$.conditions.receivedCount").value(1489))
                .andExpect(jsonPath("$.conditions.retainedCount").value(5))
                .andExpect(jsonPath("$.conditions.truncated").value(true))
                .andExpect(jsonPath("$.conditions.records[0].resourceType").value("Condition"))
                .andExpect(jsonPath("$.conditions.records[0].clinicalStatusCode").value("active"))
                .andExpect(jsonPath("$.patient.id").doesNotExist())
                .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString(PATIENT_ID))))
                .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("Patient/"))));
    }

    @Test
    void patientIdPathIsNotAConsumerSurface() throws Exception {
        mockMvc.perform(get("/api/model-boundary/v1/" + PATIENT_ID)).andExpect(status().isNotFound());
    }

    private static ModelBoundaryContract completeContract() {
        return new ModelBoundaryContract(
                ModelBoundaryContractVersion.V1,
                "oracle-health-sandbox",
                PatientContextSource.CONFIGURED,
                Instant.parse("2026-09-05T03:00:00Z"),
                ClinicalSnapshotOutcome.SNAPSHOT_COMPLETE,
                new BoundaryPatient(ClinicalSnapshotResourceStatus.SUCCESS, "Patient"),
                new BoundaryCollection<>(
                        ClinicalSnapshotResourceStatus.SUCCESS,
                        1489,
                        5,
                        true,
                        List.of(new BoundaryCondition("Condition", "active"))),
                null,
                null,
                null);
    }
}

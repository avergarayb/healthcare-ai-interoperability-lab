package lab.healthcare.fhir.agentstub.web;

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

@WebMvcTest(AgentStubController.class)
class AgentStubControllerTest {

    private static final String PATIENT_ID = "secret-patient-12724067";

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private ModelBoundaryContractProvider provider;

    @Test
    void jsonObservationIsBlindToRecordValues() throws Exception {
        when(provider.currentContract()).thenReturn(completeContract());

        mockMvc.perform(get("/api/agent-stub/v1"))
                .andExpect(status().isOk())
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_JSON))
                .andExpect(jsonPath("$.contractVersion").value("v1"))
                .andExpect(jsonPath("$.consumed").value(true))
                .andExpect(jsonPath("$.modelCalled").value(false))
                .andExpect(jsonPath("$.conditions.receivedCount").value(1489))
                .andExpect(jsonPath("$.conditions.records").doesNotExist())
                .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("active"))))
                .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString(PATIENT_ID))));
    }

    @Test
    void htmlPageIsBlindToRecordValues() throws Exception {
        when(provider.currentContract()).thenReturn(completeContract());

        mockMvc.perform(get("/lab/agent-stub"))
                .andExpect(status().isOk())
                .andExpect(content().contentTypeCompatibleWith(MediaType.TEXT_HTML))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("modelCalled=false")))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("conditionsReceivedCount=1489")))
                .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("active"))))
                .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString(PATIENT_ID))));
    }

    @Test
    void authenticationRequiredIs401() throws Exception {
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

        mockMvc.perform(get("/api/agent-stub/v1"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.outcome").value("AUTHENTICATION_REQUIRED"))
                .andExpect(jsonPath("$.modelCalled").value(false));
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
                        List.of(
                                new BoundaryCondition("Condition", "active"),
                                new BoundaryCondition("Condition", "active"),
                                new BoundaryCondition("Condition", "active"),
                                new BoundaryCondition("Condition", "active"),
                                new BoundaryCondition("Condition", "active"))),
                null,
                null,
                null);
    }
}

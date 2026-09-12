package lab.healthcare.fhir.agent.web;

import lab.healthcare.fhir.modelboundary.BoundaryCollection;
import lab.healthcare.fhir.modelboundary.BoundaryCondition;
import lab.healthcare.fhir.modelboundary.BoundaryDiagnosticReport;
import lab.healthcare.fhir.modelboundary.BoundaryObservation;
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

@WebMvcTest(DeterministicAgentController.class)
class DeterministicAgentControllerTest {

    private static final String HIDDEN_PATIENT = "lab-hidden-patient";

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private ModelBoundaryContractProvider provider;

    @Test
    void jsonVerdictIsBlindToRecordValues() throws Exception {
        when(provider.currentContract()).thenReturn(completeContract());

        mockMvc.perform(get("/api/deterministic-agent/v1"))
                .andExpect(status().isOk())
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_JSON))
                .andExpect(jsonPath("$.decision").value("READY"))
                .andExpect(jsonPath("$.reasonCode").value("READY_FOR_BOUNDARY"))
                .andExpect(jsonPath("$.requiresHumanReview").value(true))
                .andExpect(jsonPath("$.modelCalled").value(false))
                .andExpect(jsonPath("$.pipelineStatus").value("SUCCESS"))
                .andExpect(jsonPath("$.records").doesNotExist())
                .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("active"))))
                .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString(HIDDEN_PATIENT))))
                .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("access_token"))));
    }

    @Test
    void htmlPageIsBlindToRecordValues() throws Exception {
        when(provider.currentContract()).thenReturn(completeContract());

        mockMvc.perform(get("/lab/deterministic-agent"))
                .andExpect(status().isOk())
                .andExpect(content().contentTypeCompatibleWith(MediaType.TEXT_HTML))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("deterministicAgent=READY")))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("requiresHumanReview=true")))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("agentModelCalled=false")))
                .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("active"))))
                .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString(HIDDEN_PATIENT))));
    }

    @Test
    void authenticationRequiredIs401AndBlocked() throws Exception {
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

        mockMvc.perform(get("/api/deterministic-agent/v1"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.decision").value("BLOCKED"))
                .andExpect(jsonPath("$.modelCalled").value(false))
                .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("Bearer"))));
    }

    private static ModelBoundaryContract completeContract() {
        return new ModelBoundaryContract(
                ModelBoundaryContractVersion.V1,
                "oracle-health-sandbox",
                PatientContextSource.CONFIGURED,
                Instant.parse("2026-09-12T21:00:00Z"),
                ClinicalSnapshotOutcome.SNAPSHOT_COMPLETE,
                new BoundaryPatient(ClinicalSnapshotResourceStatus.SUCCESS, "Patient"),
                new BoundaryCollection<>(
                        ClinicalSnapshotResourceStatus.SUCCESS,
                        1,
                        1,
                        false,
                        List.of(new BoundaryCondition("Condition", "active"))),
                new BoundaryCollection<>(
                        ClinicalSnapshotResourceStatus.SUCCESS,
                        1,
                        1,
                        false,
                        List.of(new BoundaryObservation("Observation", "final"))),
                new BoundaryCollection<>(
                        ClinicalSnapshotResourceStatus.SUCCESS,
                        1,
                        1,
                        false,
                        List.of(new BoundaryDiagnosticReport("DiagnosticReport", "final"))),
                null);
    }
}

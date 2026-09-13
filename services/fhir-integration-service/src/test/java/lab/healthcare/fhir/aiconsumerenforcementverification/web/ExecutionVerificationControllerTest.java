package lab.healthcare.fhir.aiconsumerenforcementverification.web;

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

@WebMvcTest(AiConsumerClinicalDataEnforcementExecutionVerificationController.class)
class ExecutionVerificationControllerTest {

    private static final String HIDDEN_PATIENT = "lab-hidden-patient";

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private ModelBoundaryContractProvider provider;

    @Test
    void jsonPayloadIsBlindAndDoesNotVerifyExecution() throws Exception {
        when(provider.currentContract()).thenReturn(completeEpic());

        mockMvc.perform(get("/api/ai-consumer-clinical-data-enforcement-execution-verification/v1"))
                .andExpect(status().isOk())
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_JSON))
                .andExpect(jsonPath("$.status").value("NOT_VERIFIED_FOR_CLINICAL_DATA_ACCESS"))
                .andExpect(jsonPath("$.verificationDecisionAvailable").value(false))
                .andExpect(jsonPath("$.verificationDecisionEvaluated").value(false))
                .andExpect(jsonPath("$.executionEvidenceAvailable").value(false))
                .andExpect(jsonPath("$.executionEvidenceEvaluated").value(false))
                .andExpect(jsonPath("$.executionVerificationAvailable").value(false))
                .andExpect(jsonPath("$.executionVerificationProviderConfigured").value(false))
                .andExpect(jsonPath("$.executionVerified").value(false))
                .andExpect(jsonPath("$.clinicalDataAccessGranted").value(false))
                .andExpect(jsonPath("$.clinicalDataAccessAllowed").value(false))
                .andExpect(jsonPath("$.clinicalDataAccessEnforced").value(false))
                .andExpect(jsonPath("$.requiresHumanReview").value(true))
                .andExpect(jsonPath("$.records").doesNotExist())
                .andExpect(jsonPath("$.patientId").doesNotExist())
                .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("active"))))
                .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString(HIDDEN_PATIENT))))
                .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("access_token"))))
                .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("Bearer"))));
    }

    @Test
    void queryParametersCannotActivateVerification() throws Exception {
        when(provider.currentContract()).thenReturn(completeEpic());

        mockMvc.perform(get("/api/ai-consumer-clinical-data-enforcement-execution-verification/v1")
                        .param("executionVerified", "true")
                        .param("clinicalDataAccessGranted", "true")
                        .param("enforcementExecutionPerformed", "true")
                        .param("executionEvidenceAvailable", "true"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("NOT_VERIFIED_FOR_CLINICAL_DATA_ACCESS"))
                .andExpect(jsonPath("$.executionVerified").value(false))
                .andExpect(jsonPath("$.clinicalDataAccessGranted").value(false));
    }

    @Test
    void headersCannotActivateVerification() throws Exception {
        when(provider.currentContract()).thenReturn(completeEpic());

        mockMvc.perform(get("/api/ai-consumer-clinical-data-enforcement-execution-verification/v1")
                        .header("X-Execution-Verified", "true")
                        .header("X-Clinical-Data-Access-Granted", "true")
                        .header("X-Enforcement-Evidence", "true"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("NOT_VERIFIED_FOR_CLINICAL_DATA_ACCESS"))
                .andExpect(jsonPath("$.executionVerified").value(false))
                .andExpect(jsonPath("$.executionEvidenceAvailable").value(false));
    }

    @Test
    void htmlPageIsBlind() throws Exception {
        when(provider.currentContract()).thenReturn(completeEpic());

        mockMvc.perform(get("/lab/ai-consumer-clinical-data-enforcement-execution-verification"))
                .andExpect(status().isOk())
                .andExpect(content().contentTypeCompatibleWith(MediaType.TEXT_HTML))
                .andExpect(content().string(org.hamcrest.Matchers.containsString(
                        "aiConsumerClinicalDataEnforcementExecutionVerification=NOT_VERIFIED_FOR_CLINICAL_DATA_ACCESS")))
                .andExpect(content().string(org.hamcrest.Matchers.containsString(
                        "aiConsumerVerificationDecisionAvailable=false")))
                .andExpect(content().string(org.hamcrest.Matchers.containsString(
                        "aiConsumerExecutionVerified=false")))
                .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("active"))));
    }

    private static ModelBoundaryContract completeEpic() {
        return new ModelBoundaryContract(
                ModelBoundaryContractVersion.V1,
                "epic-sandbox",
                PatientContextSource.CONFIGURED,
                Instant.parse("2026-09-12T23:30:00Z"),
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

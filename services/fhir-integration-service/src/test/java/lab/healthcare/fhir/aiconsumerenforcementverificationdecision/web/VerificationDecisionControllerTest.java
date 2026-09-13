package lab.healthcare.fhir.aiconsumerenforcementverificationdecision.web;

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

@WebMvcTest(AiConsumerVerificationDecisionController.class)
class VerificationDecisionControllerTest {

    private static final String HIDDEN_PATIENT = "lab-hidden-patient";

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private ModelBoundaryContractProvider provider;

    @Test
    void jsonPayloadIsBlindAndDoesNotApproveVerification() throws Exception {
        when(provider.currentContract()).thenReturn(completeEpic());

        mockMvc.perform(get("/api/ai-consumer-clinical-data-enforcement-verification-decision/v1"))
                .andExpect(status().isOk())
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_JSON))
                .andExpect(jsonPath("$.status").value("VERIFICATION_DECISION_NOT_AVAILABLE"))
                .andExpect(jsonPath("$.decisionAvailable").value(false))
                .andExpect(jsonPath("$.decisionEvaluated").value(false))
                .andExpect(jsonPath("$.verificationInputAccepted").value(false))
                .andExpect(jsonPath("$.verificationEvidenceAccepted").value(false))
                .andExpect(jsonPath("$.verificationDecisionAvailable").value(false))
                .andExpect(jsonPath("$.verificationDecisionProviderConfigured").value(false))
                .andExpect(jsonPath("$.verificationApproved").value(false))
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
    void queryParametersCannotActivateDecision() throws Exception {
        when(provider.currentContract()).thenReturn(completeEpic());

        mockMvc.perform(get("/api/ai-consumer-clinical-data-enforcement-verification-decision/v1")
                        .param("verificationApproved", "true")
                        .param("clinicalDataAccessGranted", "true")
                        .param("executionVerified", "true")
                        .param("decisionAvailable", "true"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("VERIFICATION_DECISION_NOT_AVAILABLE"))
                .andExpect(jsonPath("$.verificationApproved").value(false))
                .andExpect(jsonPath("$.clinicalDataAccessGranted").value(false));
    }

    @Test
    void headersCannotActivateDecision() throws Exception {
        when(provider.currentContract()).thenReturn(completeEpic());

        mockMvc.perform(get("/api/ai-consumer-clinical-data-enforcement-verification-decision/v1")
                        .header("X-Verification-Approved", "true")
                        .header("X-Clinical-Data-Access-Granted", "true")
                        .header("X-Decision-Available", "true"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("VERIFICATION_DECISION_NOT_AVAILABLE"))
                .andExpect(jsonPath("$.verificationApproved").value(false))
                .andExpect(jsonPath("$.decisionAvailable").value(false));
    }

    @Test
    void htmlPageIsBlind() throws Exception {
        when(provider.currentContract()).thenReturn(completeEpic());

        mockMvc.perform(get("/lab/ai-consumer-clinical-data-enforcement-verification-decision"))
                .andExpect(status().isOk())
                .andExpect(content().contentTypeCompatibleWith(MediaType.TEXT_HTML))
                .andExpect(content().string(org.hamcrest.Matchers.containsString(
                        "aiConsumerClinicalDataEnforcementVerificationDecision=VERIFICATION_DECISION_NOT_AVAILABLE")))
                .andExpect(content().string(org.hamcrest.Matchers.containsString(
                        "aiConsumerDecisionAvailable=false")))
                .andExpect(content().string(org.hamcrest.Matchers.containsString(
                        "aiConsumerVerificationApproved=false")))
                .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("active"))));
    }

    private static ModelBoundaryContract completeEpic() {
        return new ModelBoundaryContract(
                ModelBoundaryContractVersion.V1,
                "epic-sandbox",
                PatientContextSource.CONFIGURED,
                Instant.parse("2026-09-13T00:20:00Z"),
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

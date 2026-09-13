package lab.healthcare.fhir.aiconsumerenforcementverificationapproval.web;

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

@WebMvcTest(AiConsumerEnforcementVerificationApprovalController.class)
class ApprovalControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private ModelBoundaryContractProvider provider;

    @Test
    void jsonPayloadIsBlindAndDoesNotApprove() throws Exception {
        when(provider.currentContract()).thenReturn(completeEpic());

        mockMvc.perform(get("/api/ai-consumer-enforcement-verification-approval/v1"))
                .andExpect(status().isOk())
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_JSON))
                .andExpect(jsonPath("$.status").value("VERIFICATION_APPROVAL_NOT_AVAILABLE"))
                .andExpect(jsonPath("$.verificationApprovalAvailable").value(false))
                .andExpect(jsonPath("$.verificationApprovalEvaluated").value(false))
                .andExpect(jsonPath("$.verificationApproved").value(false))
                .andExpect(jsonPath("$.clinicalDataAccessGranted").value(false))
                .andExpect(jsonPath("$.requiresHumanReview").value(true))
                .andExpect(jsonPath("$.patientId").doesNotExist())
                .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("active"))));
    }

    @Test
    void queryParametersAndHeadersCannotActivateApproval() throws Exception {
        when(provider.currentContract()).thenReturn(completeEpic());

        mockMvc.perform(get("/api/ai-consumer-enforcement-verification-approval/v1")
                        .param("verificationApproved", "true")
                        .param("clinicalDataAccessGranted", "true")
                        .header("X-Verification-Approved", "true"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("VERIFICATION_APPROVAL_NOT_AVAILABLE"))
                .andExpect(jsonPath("$.verificationApproved").value(false));
    }

    @Test
    void htmlPageIsBlind() throws Exception {
        when(provider.currentContract()).thenReturn(completeEpic());

        mockMvc.perform(get("/lab/ai-consumer-enforcement-verification-approval"))
                .andExpect(status().isOk())
                .andExpect(content().contentTypeCompatibleWith(MediaType.TEXT_HTML))
                .andExpect(content().string(org.hamcrest.Matchers.containsString(
                        "aiConsumerEnforcementVerificationApproval=VERIFICATION_APPROVAL_NOT_AVAILABLE")))
                .andExpect(content().string(org.hamcrest.Matchers.containsString(
                        "aiConsumerVerificationApproved=false")))
                .andExpect(content().string(org.hamcrest.Matchers.containsString(
                        "aiConsumerApprovalHumanReviewRequired=true")));
    }

    private static ModelBoundaryContract completeEpic() {
        return new ModelBoundaryContract(
                ModelBoundaryContractVersion.V1,
                "epic-sandbox",
                PatientContextSource.CONFIGURED,
                Instant.parse("2026-09-13T00:30:00Z"),
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

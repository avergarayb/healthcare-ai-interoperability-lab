package lab.healthcare.fhir.aihandoffauthorization.web;

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

@WebMvcTest(AiHandoffAuthorizationController.class)
class AiHandoffAuthorizationControllerTest {

    private static final String HIDDEN_PATIENT = "lab-hidden-patient";

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private ModelBoundaryContractProvider provider;

    @Test
    void jsonPayloadIsBlindAndDoesNotAuthorizeHandoff() throws Exception {
        when(provider.currentContract()).thenReturn(completeEpic());

        mockMvc.perform(get("/api/ai-handoff-authorization/v1"))
                .andExpect(status().isOk())
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_JSON))
                .andExpect(jsonPath("$.authorizationStatus").value("HANDOFF_NOT_AUTHORIZED"))
                .andExpect(jsonPath("$.reasonCode").value("REAL_AUTHORIZATION_NOT_IMPLEMENTED"))
                .andExpect(jsonPath("$.readinessStatus").value("READY_FOR_FUTURE_HANDOFF"))
                .andExpect(jsonPath("$.handoffAuthorized").value(false))
                .andExpect(jsonPath("$.dispatchPerformed").value(false))
                .andExpect(jsonPath("$.externalAuthorizationAvailable").value(false))
                .andExpect(jsonPath("$.modelCallAuthorized").value(false))
                .andExpect(jsonPath("$.modelCalled").value(false))
                .andExpect(jsonPath("$.processingStatus").value("NOT_EXECUTED"))
                .andExpect(jsonPath("$.dispatchStatus").value("NOT_DISPATCHED"))
                .andExpect(jsonPath("$.requiresHumanReview").value(true))
                .andExpect(jsonPath("$.records").doesNotExist())
                .andExpect(jsonPath("$.patientId").doesNotExist())
                .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("active"))))
                .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString(HIDDEN_PATIENT))))
                .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("access_token"))))
                .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("Bearer"))));
    }

    @Test
    void queryParameterAndHeaderCannotActivateAuthorization() throws Exception {
        when(provider.currentContract()).thenReturn(completeEpic());

        mockMvc.perform(get("/api/ai-handoff-authorization/v1")
                        .param("authorized", "true")
                        .param("handoffAuthorized", "true")
                        .header("X-Handoff-Authorized", "true"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.authorizationStatus").value("HANDOFF_NOT_AUTHORIZED"))
                .andExpect(jsonPath("$.handoffAuthorized").value(false))
                .andExpect(jsonPath("$.externalAuthorizationAvailable").value(false));
    }

    @Test
    void htmlPageIsBlind() throws Exception {
        when(provider.currentContract()).thenReturn(completeEpic());

        mockMvc.perform(get("/lab/ai-handoff-authorization"))
                .andExpect(status().isOk())
                .andExpect(content().contentTypeCompatibleWith(MediaType.TEXT_HTML))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("aiHandoffAuthorization=HANDOFF_NOT_AUTHORIZED")))
                .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("active"))));
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

        mockMvc.perform(get("/api/ai-handoff-authorization/v1"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.authorizationStatus").value("BLOCKED"))
                .andExpect(jsonPath("$.reasonCode").value("READINESS_BLOCKED"))
                .andExpect(jsonPath("$.handoffAuthorized").value(false))
                .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("Bearer"))));
    }

    private static ModelBoundaryContract completeEpic() {
        return new ModelBoundaryContract(
                ModelBoundaryContractVersion.V1,
                "epic-sandbox",
                PatientContextSource.CONFIGURED,
                Instant.parse("2026-09-12T22:00:00Z"),
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

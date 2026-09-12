package lab.healthcare.fhir.aiconsumerauthorization.web;

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

@WebMvcTest(AiConsumerAuthorizationController.class)
class AiConsumerAuthorizationControllerTest {

    private static final String HIDDEN_PATIENT = "lab-hidden-patient";

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private ModelBoundaryContractProvider provider;

    @Test
    void jsonPayloadIsBlindAndDoesNotGrantAuthorization() throws Exception {
        when(provider.currentContract()).thenReturn(completeEpic());

        mockMvc.perform(get("/api/ai-consumer-authorization/v1"))
                .andExpect(status().isOk())
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_JSON))
                .andExpect(jsonPath("$.status").value("AUTHORIZATION_NOT_IMPLEMENTED"))
                .andExpect(jsonPath("$.authenticationVerified").value(false))
                .andExpect(jsonPath("$.authorizationGranted").value(false))
                .andExpect(jsonPath("$.consumerAuthorizationAvailable").value(false))
                .andExpect(jsonPath("$.realSecurityProviderConfigured").value(false))
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
    void queryParametersCannotActivateAuthorization() throws Exception {
        when(provider.currentContract()).thenReturn(completeEpic());

        mockMvc.perform(get("/api/ai-consumer-authorization/v1")
                        .param("authorized", "true")
                        .param("authenticated", "true")
                        .param("allow", "true")
                        .param("dispatch", "true")
                        .param("handoff", "true"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("AUTHORIZATION_NOT_IMPLEMENTED"))
                .andExpect(jsonPath("$.authorizationGranted").value(false))
                .andExpect(jsonPath("$.authenticationVerified").value(false))
                .andExpect(jsonPath("$.handoffAuthorized").value(false));
    }

    @Test
    void headersCannotActivateAuthorization() throws Exception {
        when(provider.currentContract()).thenReturn(completeEpic());

        mockMvc.perform(get("/api/ai-consumer-authorization/v1")
                        .header("X-Authorized", "true")
                        .header("X-Authenticated", "true")
                        .header("X-Allow-Handoff", "true")
                        .header("X-Consumer-Scope", "ai.handoff.request"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("AUTHORIZATION_NOT_IMPLEMENTED"))
                .andExpect(jsonPath("$.authorizationGranted").value(false))
                .andExpect(jsonPath("$.handoffAuthorized").value(false));
    }

    @Test
    void htmlPageIsBlind() throws Exception {
        when(provider.currentContract()).thenReturn(completeEpic());

        mockMvc.perform(get("/lab/ai-consumer-authorization"))
                .andExpect(status().isOk())
                .andExpect(content().contentTypeCompatibleWith(MediaType.TEXT_HTML))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("aiConsumerAuthorization=AUTHORIZATION_NOT_IMPLEMENTED")))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("aiConsumerAuthentication=NOT_AUTHENTICATED")))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("aiConsumerAuthorizationAvailable=false")))
                .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("active"))));
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

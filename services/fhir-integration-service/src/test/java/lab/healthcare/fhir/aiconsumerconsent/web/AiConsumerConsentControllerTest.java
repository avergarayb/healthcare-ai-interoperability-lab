package lab.healthcare.fhir.aiconsumerconsent.web;

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

@WebMvcTest(AiConsumerConsentController.class)
class AiConsumerConsentControllerTest {

    private static final String HIDDEN_PATIENT = "lab-hidden-patient";

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private ModelBoundaryContractProvider provider;

    @Test
    void jsonPayloadIsBlindAndDoesNotGrantConsent() throws Exception {
        when(provider.currentContract()).thenReturn(completeEpic());

        mockMvc.perform(get("/api/ai-consumer-consent/v1"))
                .andExpect(status().isOk())
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_JSON))
                .andExpect(jsonPath("$.status").value("CONSENT_NOT_IMPLEMENTED"))
                .andExpect(jsonPath("$.consentVerified").value(false))
                .andExpect(jsonPath("$.purposeApproved").value(false))
                .andExpect(jsonPath("$.dataScopeApproved").value(false))
                .andExpect(jsonPath("$.consentAvailable").value(false))
                .andExpect(jsonPath("$.clinicalDataAccessAllowed").value(false))
                .andExpect(jsonPath("$.consentProviderConfigured").value(false))
                .andExpect(jsonPath("$.consumerAuthorizationAvailable").value(false))
                .andExpect(jsonPath("$.authorizationGranted").value(false))
                .andExpect(jsonPath("$.handoffAuthorized").value(false))
                .andExpect(jsonPath("$.dispatchPerformed").value(false))
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
    void queryParametersCannotActivateConsent() throws Exception {
        when(provider.currentContract()).thenReturn(completeEpic());

        mockMvc.perform(get("/api/ai-consumer-consent/v1")
                        .param("consent", "true")
                        .param("consentVerified", "true")
                        .param("purposeApproved", "true")
                        .param("dataScopeApproved", "true")
                        .param("allow", "true")
                        .param("dispatch", "true")
                        .param("handoff", "true"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("CONSENT_NOT_IMPLEMENTED"))
                .andExpect(jsonPath("$.consentVerified").value(false))
                .andExpect(jsonPath("$.purposeApproved").value(false))
                .andExpect(jsonPath("$.dataScopeApproved").value(false))
                .andExpect(jsonPath("$.clinicalDataAccessAllowed").value(false))
                .andExpect(jsonPath("$.handoffAuthorized").value(false));
    }

    @Test
    void headersCannotActivateConsent() throws Exception {
        when(provider.currentContract()).thenReturn(completeEpic());

        mockMvc.perform(get("/api/ai-consumer-consent/v1")
                        .header("X-Consent-Verified", "true")
                        .header("X-Purpose-Approved", "true")
                        .header("X-Data-Scope-Approved", "true")
                        .header("X-Allow-Clinical-Access", "true"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("CONSENT_NOT_IMPLEMENTED"))
                .andExpect(jsonPath("$.consentVerified").value(false))
                .andExpect(jsonPath("$.purposeApproved").value(false))
                .andExpect(jsonPath("$.clinicalDataAccessAllowed").value(false));
    }

    @Test
    void htmlPageIsBlind() throws Exception {
        when(provider.currentContract()).thenReturn(completeEpic());

        mockMvc.perform(get("/lab/ai-consumer-consent"))
                .andExpect(status().isOk())
                .andExpect(content().contentTypeCompatibleWith(MediaType.TEXT_HTML))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("aiConsumerConsent=CONSENT_NOT_IMPLEMENTED")))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("aiConsumerPurpose=PURPOSE_NOT_VERIFIED")))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("aiConsumerDataScope=DATA_SCOPE_NOT_VERIFIED")))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("aiConsumerConsentAvailable=false")))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("aiClinicalDataAccessAllowed=false")))
                .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("active"))));
    }

    private static ModelBoundaryContract completeEpic() {
        return new ModelBoundaryContract(
                ModelBoundaryContractVersion.V1,
                "epic-sandbox",
                PatientContextSource.CONFIGURED,
                Instant.parse("2026-09-12T23:00:00Z"),
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

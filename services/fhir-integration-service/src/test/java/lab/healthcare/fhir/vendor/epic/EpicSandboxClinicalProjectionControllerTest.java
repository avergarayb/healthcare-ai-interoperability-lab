package lab.healthcare.fhir.vendor.epic;

import lab.healthcare.fhir.patient.PatientContextSource;
import lab.healthcare.fhir.projection.ClinicalProjectionResult;
import lab.healthcare.fhir.projection.ProjectedCollection;
import lab.healthcare.fhir.projection.RetainedCondition;
import lab.healthcare.fhir.projection.RetainedDiagnosticReport;
import lab.healthcare.fhir.projection.RetainedObservation;
import lab.healthcare.fhir.projection.RetainedPatient;
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

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(EpicSandboxClinicalProjectionController.class)
class EpicSandboxClinicalProjectionControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private EpicSandboxClinicalProjectionService projectionService;

    @MockitoBean
    private EpicIntegrationProfile profile;

    @Test
    void successPageIsBlind() throws Exception {
        when(projectionService.assemble(any()))
                .thenReturn(new ClinicalProjectionResult(
                        ClinicalSnapshotOutcome.SNAPSHOT_COMPLETE,
                        EpicIntegrationProfile.SANDBOX_SERVER,
                        PatientContextSource.CONFIGURED,
                        Instant.parse("2026-09-12T18:00:00Z"),
                        ClinicalSnapshotResourceStatus.SUCCESS,
                        new RetainedPatient("Patient"),
                        ProjectedCollection.retained(
                                1, 1, false, List.of(new RetainedCondition("Condition", "active"))),
                        ProjectedCollection.retained(
                                2,
                                2,
                                false,
                                List.of(
                                        new RetainedObservation("Observation", "final"),
                                        new RetainedObservation("Observation", "final"))),
                        ProjectedCollection.retained(
                                1,
                                1,
                                false,
                                List.of(new RetainedDiagnosticReport("DiagnosticReport", "final"))),
                        null,
                        "Controlled clinical projection succeeded"));

        mockMvc.perform(get("/epic/sandbox/fhir/clinical-projection"))
                .andExpect(status().isOk())
                .andExpect(content().contentTypeCompatibleWith(MediaType.TEXT_HTML))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("status=SUCCESS")))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("destination=epic-sandbox")))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("clinicalSnapshot=SUCCEEDED")))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("controlledProjection=SUCCEEDED")))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("modelBoundaryContract=v1")))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("modelBoundary=SUCCEEDED")))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("agentStub=SUCCEEDED")))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("sensitiveFieldsExposed=false")))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("rawFhirExposed=false")))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("hasClinicalData=true")))
                .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("access_token"))))
                .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("\"resourceType\""))))
                .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("active"))))
                .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("final"))))
                .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("medicationRequest"))));
    }

    @Test
    void missingContextIsConflict() throws Exception {
        when(projectionService.assemble(any()))
                .thenReturn(ClinicalProjectionResult.contextNotConfigured(EpicIntegrationProfile.SANDBOX_SERVER));

        mockMvc.perform(get("/epic/sandbox/fhir/clinical-projection"))
                .andExpect(status().isConflict())
                .andExpect(content().string(org.hamcrest.Matchers.containsString("status=FAILED")))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("PATIENT_CONTEXT_NOT_CONFIGURED")))
                .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("access_token"))));
    }

    @Test
    void missingTokenIsUnauthorized() throws Exception {
        when(projectionService.assemble(any()))
                .thenReturn(ClinicalProjectionResult.authenticationRequired(
                        EpicIntegrationProfile.SANDBOX_SERVER, "No usable access token"));

        mockMvc.perform(get("/epic/sandbox/fhir/clinical-projection"))
                .andExpect(status().isUnauthorized())
                .andExpect(content().string(org.hamcrest.Matchers.containsString("AUTHENTICATION_REQUIRED")))
                .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("Bearer"))));
    }
}

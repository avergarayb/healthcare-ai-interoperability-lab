package lab.healthcare.fhir.vendor.epic;

import lab.healthcare.fhir.exception.FhirErrorCategory;
import lab.healthcare.fhir.patient.PatientContextSource;
import lab.healthcare.fhir.routing.FhirPatientReadOutcome;
import lab.healthcare.fhir.routing.FhirPatientReadResult;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(EpicSandboxPatientContextController.class)
class EpicSandboxPatientContextControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private EpicSandboxPatientContextService patientContextService;

    @MockitoBean
    private EpicIntegrationProfile profile;

    @Test
    void successPageIsBlind() throws Exception {
        when(patientContextService.readPatient(any()))
                .thenReturn(new FhirPatientReadResult(
                        FhirPatientReadOutcome.PATIENT_READ_SUCCEEDED,
                        EpicIntegrationProfile.SANDBOX_SERVER,
                        "Patient",
                        "Patient",
                        200,
                        null,
                        PatientContextSource.CONFIGURED,
                        true,
                        "Authenticated Patient read succeeded"));

        mockMvc.perform(get("/epic/sandbox/fhir/patient"))
                .andExpect(status().isOk())
                .andExpect(content().contentTypeCompatibleWith(MediaType.TEXT_HTML))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("status=SUCCESS")))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("patientRead=SUCCEEDED")))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("destination=epic-sandbox")))
                .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("access_token"))))
                .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("\"resourceType\""))))
                .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("birthDate"))));
    }

    @Test
    void missingContextIsConflict() throws Exception {
        when(patientContextService.readPatient(any()))
                .thenReturn(FhirPatientReadResult.contextNotConfigured(EpicIntegrationProfile.SANDBOX_SERVER));

        mockMvc.perform(get("/epic/sandbox/fhir/patient"))
                .andExpect(status().isConflict())
                .andExpect(content().string(org.hamcrest.Matchers.containsString("status=FAILED")))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("PATIENT_CONTEXT_NOT_CONFIGURED")))
                .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("access_token"))));
    }

    @Test
    void missingTokenIsUnauthorized() throws Exception {
        when(patientContextService.readPatient(any()))
                .thenReturn(FhirPatientReadResult.authenticationRequired(
                        EpicIntegrationProfile.SANDBOX_SERVER, "No usable access token"));

        mockMvc.perform(get("/epic/sandbox/fhir/patient"))
                .andExpect(status().isUnauthorized())
                .andExpect(content().string(org.hamcrest.Matchers.containsString("AUTHENTICATION_REQUIRED")))
                .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("Bearer"))));
    }

    @Test
    void authorizationDeniedIsForbidden() throws Exception {
        when(patientContextService.readPatient(any()))
                .thenReturn(new FhirPatientReadResult(
                        FhirPatientReadOutcome.AUTHORIZATION_DENIED,
                        EpicIntegrationProfile.SANDBOX_SERVER,
                        "Patient",
                        "",
                        403,
                        FhirErrorCategory.AUTHORIZATION_ERROR,
                        PatientContextSource.CONFIGURED,
                        true,
                        FhirErrorCategory.AUTHORIZATION_ERROR.safeMessage()));

        mockMvc.perform(get("/epic/sandbox/fhir/patient"))
                .andExpect(status().isForbidden())
                .andExpect(content().string(org.hamcrest.Matchers.containsString("AUTHORIZATION_DENIED")));
    }
}

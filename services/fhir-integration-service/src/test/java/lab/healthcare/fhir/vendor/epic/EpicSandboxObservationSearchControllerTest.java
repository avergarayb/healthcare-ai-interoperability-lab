package lab.healthcare.fhir.vendor.epic;

import lab.healthcare.fhir.exception.FhirErrorCategory;
import lab.healthcare.fhir.patient.PatientContextSource;
import lab.healthcare.fhir.routing.FhirObservationSearchOutcome;
import lab.healthcare.fhir.routing.FhirObservationSearchResult;

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

@WebMvcTest(EpicSandboxObservationSearchController.class)
class EpicSandboxObservationSearchControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private EpicSandboxObservationSearchService observationSearchService;

    @MockitoBean
    private EpicIntegrationProfile profile;

    @Test
    void successPageIsBlind() throws Exception {
        when(observationSearchService.searchObservations(any()))
                .thenReturn(new FhirObservationSearchResult(
                        FhirObservationSearchOutcome.OBSERVATION_SEARCH_SUCCEEDED,
                        EpicIntegrationProfile.SANDBOX_SERVER,
                        "Observation",
                        "Bundle",
                        200,
                        null,
                        PatientContextSource.CONFIGURED,
                        true,
                        true,
                        "Authenticated Observation search succeeded"));

        mockMvc.perform(get("/epic/sandbox/fhir/observation-search"))
                .andExpect(status().isOk())
                .andExpect(content().contentTypeCompatibleWith(MediaType.TEXT_HTML))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("status=SUCCESS")))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("observationSearch=SUCCEEDED")))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("destination=epic-sandbox")))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("hasEntries=true")))
                .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("access_token"))))
                .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("\"resourceType\""))))
                .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("valueQuantity"))));
    }

    @Test
    void missingContextIsConflict() throws Exception {
        when(observationSearchService.searchObservations(any()))
                .thenReturn(FhirObservationSearchResult.contextNotConfigured(EpicIntegrationProfile.SANDBOX_SERVER));

        mockMvc.perform(get("/epic/sandbox/fhir/observation-search"))
                .andExpect(status().isConflict())
                .andExpect(content().string(org.hamcrest.Matchers.containsString("status=FAILED")))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("PATIENT_CONTEXT_NOT_CONFIGURED")))
                .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("access_token"))));
    }

    @Test
    void missingTokenIsUnauthorized() throws Exception {
        when(observationSearchService.searchObservations(any()))
                .thenReturn(FhirObservationSearchResult.authenticationRequired(
                        EpicIntegrationProfile.SANDBOX_SERVER, "No usable access token"));

        mockMvc.perform(get("/epic/sandbox/fhir/observation-search"))
                .andExpect(status().isUnauthorized())
                .andExpect(content().string(org.hamcrest.Matchers.containsString("AUTHENTICATION_REQUIRED")))
                .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("Bearer"))));
    }

    @Test
    void authorizationDeniedIsForbidden() throws Exception {
        when(observationSearchService.searchObservations(any()))
                .thenReturn(new FhirObservationSearchResult(
                        FhirObservationSearchOutcome.AUTHORIZATION_DENIED,
                        EpicIntegrationProfile.SANDBOX_SERVER,
                        "Observation",
                        "",
                        403,
                        FhirErrorCategory.AUTHORIZATION_ERROR,
                        PatientContextSource.CONFIGURED,
                        true,
                        null,
                        FhirErrorCategory.AUTHORIZATION_ERROR.safeMessage()));

        mockMvc.perform(get("/epic/sandbox/fhir/observation-search"))
                .andExpect(status().isForbidden())
                .andExpect(content().string(org.hamcrest.Matchers.containsString("AUTHORIZATION_DENIED")));
    }
}

package lab.healthcare.fhir.vendor.epic;

import lab.healthcare.fhir.smart.SmartAuthorizationStart;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import java.time.Instant;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(EpicSandboxSmartInteractiveController.class)
class EpicSandboxSmartInteractiveControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private EpicSandboxAuthenticationService authenticationService;

    @MockitoBean
    private EpicIntegrationProfile profile;

    @Test
    void disabledStartIsConflictAndDoesNotExposeSecrets() throws Exception {
        when(profile.enabled()).thenReturn(false);
        when(profile.serverProfileName()).thenReturn(EpicIntegrationProfile.SANDBOX_SERVER);
        when(authenticationService.startAuthorization(any()))
                .thenThrow(new EpicProfileException("Epic sandbox profile is disabled"));

        mockMvc.perform(get("/epic/sandbox/smart/start"))
                .andExpect(status().isConflict())
                .andExpect(content().contentTypeCompatibleWith(MediaType.TEXT_HTML))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("Epic sandbox is not ready")))
                .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("access_token"))))
                .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("client_secret"))));
    }

    @Test
    void startPageShowsAuthorizationUrlWithoutToken() throws Exception {
        when(authenticationService.startAuthorization(any()))
                .thenReturn(new SmartAuthorizationStart(
                        EpicIntegrationProfile.SANDBOX_SERVER,
                        "http://127.0.0.1/does-not-contact-epic/authorize?code_challenge_method=S256",
                        "lab-state",
                        Instant.parse("2026-09-08T00:00:00Z")));

        mockMvc.perform(get("/epic/sandbox/smart/start"))
                .andExpect(status().isOk())
                .andExpect(content().string(org.hamcrest.Matchers.containsString("destination=epic-sandbox")))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("code_challenge_method=S256")))
                .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("access_token"))));
    }

    @Test
    void instructionsPageDoesNotReadPatient() throws Exception {
        mockMvc.perform(get("/epic/sandbox/smart"))
                .andExpect(status().isOk())
                .andExpect(content().string(org.hamcrest.Matchers.containsString("/epic/sandbox/smart/start")))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("does not read Patient")))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("/epic/sandbox/fhir/capabilities")))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("/epic/sandbox/fhir/patient")))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("/epic/sandbox/fhir/condition-search")))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("/epic/sandbox/fhir/observation-search")))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("/epic/sandbox/fhir/diagnostic-report-search")))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("/epic/sandbox/fhir/clinical-snapshot")));
    }
}

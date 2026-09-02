package lab.healthcare.fhir.smart.web;

import lab.healthcare.fhir.auth.AccessToken;
import lab.healthcare.fhir.smart.SmartAuthorizationCoordinator;
import lab.healthcare.fhir.smart.SmartAuthorizationException;
import lab.healthcare.fhir.smart.SmartTokenAuthenticationIncompatibility;
import lab.healthcare.fhir.smart.SmartTokenExchangeDiagnoser;
import lab.healthcare.fhir.smart.SmartTokenExchangeDiagnosis;
import lab.healthcare.fhir.smart.SmartTokenExchangeResult;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import java.time.Instant;
import java.util.List;

import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(SmartAuthorizationCallbackController.class)
class SmartAuthorizationCallbackControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private SmartAuthorizationCoordinator coordinator;

    @Test
    void missingStateIsRejectedWithoutShowingACode() throws Exception {
        when(coordinator.completeDiagnosed(anyString()))
                .thenThrow(new SmartAuthorizationException("SMART authorization failed: missing state"));

        mockMvc.perform(get("/smart/callback").queryParam("code", "must-not-appear"))
                .andExpect(status().isBadRequest())
                .andExpect(content().string(org.hamcrest.Matchers.containsString("missing state")))
                .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("must-not-appear"))));
    }

    @Test
    void confidentialRejectionRendersDiagnosisWithoutToken() throws Exception {
        when(coordinator.completeDiagnosed(anyString()))
                .thenReturn(new SmartTokenExchangeResult(
                        null,
                        SmartTokenExchangeDiagnoser.fromTokenFailure(
                                new lab.healthcare.fhir.auth.oauth2.OAuth2TokenException(
                                        "OAuth token acquisition failed: HTTP 401 invalid_client",
                                        401,
                                        "invalid_client",
                                        null),
                                List.of("client_secret_basic", "private_key_jwt"))));

        mockMvc.perform(get("/smart/callback").queryParam("code", "secret-code").queryParam("state", "lab-state"))
                .andExpect(status().isConflict())
                .andExpect(content().string(org.hamcrest.Matchers.containsString("CONFIDENTIAL_CLIENT_REQUIRED")))
                .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("secret-code"))));
    }

    @Test
    void successfulExchangeDoesNotRenderTokenValue() throws Exception {
        AccessToken token = new AccessToken(
                "must-not-render", Instant.parse("2026-09-01T13:00:00Z"), null, "user/Patient.read", null);
        when(coordinator.completeDiagnosed(anyString()))
                .thenReturn(new SmartTokenExchangeResult(
                        token, SmartTokenExchangeDiagnosis.issued(List.of())));

        mockMvc.perform(get("/smart/callback").queryParam("code", "auth-code").queryParam("state", "lab-state"))
                .andExpect(status().isOk())
                .andExpect(content().string(org.hamcrest.Matchers.containsString("hasAccessToken=true")))
                .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("must-not-render"))));
    }
}

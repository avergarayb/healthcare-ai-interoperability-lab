package lab.healthcare.fhir.vendor.epic;

import lab.healthcare.fhir.capability.FhirInteraction;
import lab.healthcare.fhir.capability.FhirResourceCapabilities;
import lab.healthcare.fhir.capability.FhirServerCapabilities;
import lab.healthcare.fhir.exception.FhirClientException;
import lab.healthcare.fhir.exception.FhirErrorCategory;
import lab.healthcare.fhir.exception.FhirErrorDetails;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import java.util.Map;
import java.util.Set;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(EpicSandboxCapabilityController.class)
class EpicSandboxCapabilityControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private EpicSandboxCapabilityDiscoveryService capabilityDiscovery;

    @MockitoBean
    private EpicIntegrationProfile profile;

    @Test
    void successPageShowsCountsWithoutTokenOrJson() throws Exception {
        when(capabilityDiscovery.discover(any()))
                .thenReturn(new FhirServerCapabilities(
                        EpicIntegrationProfile.SANDBOX_SERVER,
                        "4.0.1",
                        "",
                        "",
                        Map.of(
                                "Patient",
                                new FhirResourceCapabilities(
                                        "Patient", Set.of(FhirInteraction.READ, FhirInteraction.SEARCH_TYPE)))));

        mockMvc.perform(get("/epic/sandbox/fhir/capabilities"))
                .andExpect(status().isOk())
                .andExpect(content().contentTypeCompatibleWith(MediaType.TEXT_HTML))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("status=SUCCESS")))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("httpStatus=200")))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("fhirVersion=4.0.1")))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("resourceTypes=1")))
                .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("access_token"))))
                .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("\"resourceType\""))));
    }

    @Test
    void disabledProfileIsConflictAndDoesNotExposeSecrets() throws Exception {
        when(profile.enabled()).thenReturn(false);
        when(profile.serverProfileName()).thenReturn(EpicIntegrationProfile.SANDBOX_SERVER);
        when(capabilityDiscovery.discover(any()))
                .thenThrow(new EpicProfileException("Epic sandbox profile is disabled"));

        mockMvc.perform(get("/epic/sandbox/fhir/capabilities"))
                .andExpect(status().isConflict())
                .andExpect(content().string(org.hamcrest.Matchers.containsString("status=FAILED")))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("httpStatus=409")))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("EPIC_SANDBOX_ENABLED")))
                .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("access_token"))))
                .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("client_secret"))));
    }

    @Test
    void unauthenticatedMetadataRejectionIsUnauthorized() throws Exception {
        when(profile.serverProfileName()).thenReturn(EpicIntegrationProfile.SANDBOX_SERVER);
        when(capabilityDiscovery.discover(any()))
                .thenThrow(new FhirClientException(
                        FhirErrorDetails.of(FhirErrorCategory.AUTHENTICATION_ERROR, 401), null));

        mockMvc.perform(get("/epic/sandbox/fhir/capabilities"))
                .andExpect(status().isUnauthorized())
                .andExpect(content().string(org.hamcrest.Matchers.containsString("status=FAILED")))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("httpStatus=401")))
                .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("access_token"))))
                .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("Bearer"))));
    }
}

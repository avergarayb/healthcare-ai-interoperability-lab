package lab.healthcare.fhir.modelboundary.web;

import lab.healthcare.fhir.modelboundary.ModelBoundaryContract;
import lab.healthcare.fhir.modelboundary.ModelBoundaryContractProvider;
import lab.healthcare.fhir.modelboundary.ModelBoundaryContractVersion;
import lab.healthcare.fhir.modelboundary.ModelBoundaryServiceTokenSettings;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotOutcome;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(ModelBoundaryContractController.class)
@Import({ModelBoundaryServiceAuthConfiguration.class, ModelBoundaryServiceTokenSettings.class})
@TestPropertySource(properties = "MODEL_BOUNDARY_SERVICE_TOKEN=" + ModelBoundaryServiceTokenSettings.TEST_DUMMY)
class ModelBoundaryServiceAuthFilterTest {

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private ModelBoundaryContractProvider provider;

    @Test
    void missingHeaderIs401WithoutContract() throws Exception {
        mockMvc.perform(get("/api/model-boundary/v1"))
                .andExpect(status().isUnauthorized())
                .andExpect(content().string(""));
        verify(provider, never()).currentContract();
    }

    @Test
    void emptyHeaderIs401WithoutContract() throws Exception {
        mockMvc.perform(get("/api/model-boundary/v1").header(ModelBoundaryServiceTokenSettings.HEADER, "  "))
                .andExpect(status().isUnauthorized())
                .andExpect(content().string(""));
        verify(provider, never()).currentContract();
    }

    @Test
    void invalidTokenIs401WithoutContract() throws Exception {
        mockMvc.perform(get("/api/model-boundary/v1").header(ModelBoundaryServiceTokenSettings.HEADER, "invalid-token"))
                .andExpect(status().isUnauthorized())
                .andExpect(content().string(""));
        verify(provider, never()).currentContract();
    }

    @Test
    void validTokenWithCompleteMockIs200() throws Exception {
        when(provider.currentContract())
                .thenReturn(new ModelBoundaryContract(
                        ModelBoundaryContractVersion.V1,
                        "oracle-health-sandbox",
                        null,
                        null,
                        ClinicalSnapshotOutcome.SNAPSHOT_COMPLETE,
                        null,
                        null,
                        null,
                        null,
                        null));

        mockMvc.perform(get("/api/model-boundary/v1")
                        .header(ModelBoundaryServiceTokenSettings.HEADER, ModelBoundaryServiceTokenSettings.TEST_DUMMY))
                .andExpect(status().isOk())
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_JSON))
                .andExpect(jsonPath("$.outcome").value("SNAPSHOT_COMPLETE"));
    }

    @Test
    void validTokenWithSmartAuthenticationRequiredIs401WithContract() throws Exception {
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

        mockMvc.perform(get("/api/model-boundary/v1")
                        .header(ModelBoundaryServiceTokenSettings.HEADER, ModelBoundaryServiceTokenSettings.TEST_DUMMY))
                .andExpect(status().isUnauthorized())
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_JSON))
                .andExpect(jsonPath("$.outcome").value("AUTHENTICATION_REQUIRED"));
    }
}

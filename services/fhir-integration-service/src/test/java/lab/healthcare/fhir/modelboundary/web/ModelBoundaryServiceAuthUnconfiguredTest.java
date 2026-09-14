package lab.healthcare.fhir.modelboundary.web;

import lab.healthcare.fhir.modelboundary.ModelBoundaryContractProvider;
import lab.healthcare.fhir.modelboundary.ModelBoundaryServiceTokenSettings;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(ModelBoundaryContractController.class)
@Import({ModelBoundaryServiceAuthConfiguration.class, ModelBoundaryServiceTokenSettings.class})
@TestPropertySource(properties = "MODEL_BOUNDARY_SERVICE_TOKEN=")
class ModelBoundaryServiceAuthUnconfiguredTest {

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private ModelBoundaryContractProvider provider;

    @Test
    void missingConfiguredTokenRejectsEvenWithHeader() throws Exception {
        mockMvc.perform(get("/api/model-boundary/v1")
                        .header(ModelBoundaryServiceTokenSettings.HEADER, ModelBoundaryServiceTokenSettings.TEST_DUMMY))
                .andExpect(status().isUnauthorized())
                .andExpect(content().string(""));
        verify(provider, never()).currentContract();
    }
}

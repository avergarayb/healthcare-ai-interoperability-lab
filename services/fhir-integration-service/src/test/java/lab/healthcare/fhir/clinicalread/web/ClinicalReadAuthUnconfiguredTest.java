package lab.healthcare.fhir.clinicalread.web;

import lab.healthcare.fhir.clinicalread.ClinicalReadService;
import lab.healthcare.fhir.modelboundary.ModelBoundaryServiceTokenSettings;
import lab.healthcare.fhir.routing.RoutingService;
import lab.healthcare.fhir.server.FhirServersProperties;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Import;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import java.util.Map;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(ClinicalReadController.class)
@Import({
    ClinicalReadController.class,
    ClinicalReadService.class,
    ClinicalReadAuthConfiguration.class,
    ModelBoundaryServiceTokenSettings.class,
    ClinicalReadAuthUnconfiguredTest.LocalHapi.class
})
@TestPropertySource(properties = "MODEL_BOUNDARY_SERVICE_TOKEN=")
class ClinicalReadAuthUnconfiguredTest {

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private RoutingService routing;

    @Test
    void blankTokenRejectsAPresentedHeader() throws Exception {
        mockMvc.perform(get("/api/clinical-read/v1/appointments")
                        .param("patient", "pat-1")
                        .header(ModelBoundaryServiceTokenSettings.HEADER, ModelBoundaryServiceTokenSettings.TEST_DUMMY))
                .andExpect(status().isUnauthorized())
                .andExpect(content().string(""));
        verify(routing, never()).searchAppointmentsByPatient(any(), any(), anyInt());
    }

    @Configuration
    static class LocalHapi {
        @Bean
        FhirServersProperties fhirServersProperties() {
            return new FhirServersProperties("local-hapi", Map.of());
        }
    }
}

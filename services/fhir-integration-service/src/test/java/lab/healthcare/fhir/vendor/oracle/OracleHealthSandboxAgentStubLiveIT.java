package lab.healthcare.fhir.vendor.oracle;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.web.servlet.MvcResult;
import org.springframework.test.web.servlet.MockMvc;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assumptions.assumeThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;

@EnabledIfEnvironmentVariable(named = "ORACLE_HEALTH_LIVE_IT", matches = "true")
@SpringBootTest
@AutoConfigureMockMvc
class OracleHealthSandboxAgentStubLiveIT {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private OracleHealthIntegrationProfile oracleHealthSandboxProfile;

    @Autowired
    private ObjectMapper objectMapper;

    @Test
    void stubConsumesContractWithoutRepublishingRecords() throws Exception {
        assumeThat(oracleHealthSandboxProfile.enabled()).isTrue();
        assumeThat(oracleHealthSandboxProfile.fhirBaseUrl()).isNotBlank();

        MvcResult result = mockMvc.perform(get("/api/agent-stub/v1")).andReturn();
        JsonNode body = objectMapper.readTree(result.getResponse().getContentAsString());

        assertThat(body.path("consumed").asBoolean()).isTrue();
        assertThat(body.path("modelCalled").asBoolean()).isFalse();
        assertThat(body.path("conditions").has("records")).isFalse();
        assertThat(body.toString()).doesNotContain("access_token");
        assertThat(body.toString()).doesNotContain("Patient/");
        if (oracleHealthSandboxProfile.hasConfiguredPatientId()) {
            assertThat(body.toString()).doesNotContain(oracleHealthSandboxProfile.configuredPatientId());
        }
    }
}

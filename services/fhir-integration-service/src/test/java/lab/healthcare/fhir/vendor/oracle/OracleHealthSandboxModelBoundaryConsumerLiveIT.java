package lab.healthcare.fhir.vendor.oracle;

import lab.healthcare.fhir.modelboundary.ModelBoundaryContractVersion;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotOutcome;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assumptions.assumeThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;

/**
 * Opt-in consumer surface. Excluded from {@code -Pintegration}.
 * Run with {@code mvn verify -Poracle-live} and {@code ORACLE_HEALTH_LIVE_IT=true}.
 */
@EnabledIfEnvironmentVariable(named = "ORACLE_HEALTH_LIVE_IT", matches = "true")
@SpringBootTest
@AutoConfigureMockMvc
class OracleHealthSandboxModelBoundaryConsumerLiveIT {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private OracleHealthIntegrationProfile oracleHealthSandboxProfile;

    @Autowired
    private ObjectMapper objectMapper;

    @Test
    void consumerSurfaceReturnsVersionedContractWithoutPatientId() throws Exception {
        assumeThat(oracleHealthSandboxProfile.enabled()).isTrue();
        assumeThat(oracleHealthSandboxProfile.fhirBaseUrl()).isNotBlank();

        MvcResult result = mockMvc.perform(get("/api/model-boundary/v1"))
                .andReturn();
        JsonNode body = objectMapper.readTree(result.getResponse().getContentAsString());

        assertThat(result.getResponse().getContentType()).contains(MediaType.APPLICATION_JSON_VALUE);
        assertThat(body.path("contractVersion").asText()).isEqualTo(ModelBoundaryContractVersion.V1);
        assertThat(body.path("outcome").asText()).isIn(
                ClinicalSnapshotOutcome.PATIENT_CONTEXT_NOT_CONFIGURED.name(),
                ClinicalSnapshotOutcome.AUTHENTICATION_REQUIRED.name(),
                ClinicalSnapshotOutcome.SNAPSHOT_COMPLETE.name(),
                ClinicalSnapshotOutcome.SNAPSHOT_PARTIAL.name(),
                ClinicalSnapshotOutcome.SNAPSHOT_UNAVAILABLE.name());
        assertThat(body.toString()).doesNotContain("access_token");
        assertThat(body.toString()).doesNotContain("Bearer ");
        assertThat(body.toString()).doesNotContain("Patient/");
        if (oracleHealthSandboxProfile.hasConfiguredPatientId()) {
            assertThat(body.toString()).doesNotContain(oracleHealthSandboxProfile.configuredPatientId());
        }
        JsonNode conditions = body.path("conditions");
        if (conditions.hasNonNull("receivedCount") && conditions.path("receivedCount").asInt() > 5) {
            assertThat(conditions.path("retainedCount").asInt()).isEqualTo(5);
            assertThat(conditions.path("truncated").asBoolean()).isTrue();
            assertThat(conditions.path("records")).hasSize(5);
        }
    }
}

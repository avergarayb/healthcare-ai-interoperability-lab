package lab.healthcare.fhir.vendor.oracle;

import lab.healthcare.fhir.client.FhirService;
import lab.healthcare.fhir.routing.FhirConditionSearchOutcome;
import lab.healthcare.fhir.routing.FhirConditionSearchResult;
import lab.healthcare.fhir.server.FhirServerProfile;
import lab.healthcare.fhir.vendor.FhirVendor;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
class OracleHealthSandboxConditionSearchIT {

    @Autowired
    private OracleSandboxConditionSearchService oracleSandboxConditionSearchService;

    @Autowired
    private OracleHealthIntegrationProfile oracleHealthSandboxProfile;

    @Autowired
    private FhirServerProfile activeFhirServerProfile;

    @Autowired
    private FhirService fhirService;

    @Test
    void defaultDisabledOracleDoesNotSearchConditions() {
        assertThat(activeFhirServerProfile.name()).isEqualTo("local-hapi");
        assertThat(activeFhirServerProfile.vendor()).isEqualTo(FhirVendor.GENERIC);
        assertThat(oracleHealthSandboxProfile.enabled()).isFalse();
        assertThat(oracleHealthSandboxProfile.hasConfiguredPatientId()).isFalse();

        FhirConditionSearchResult result =
                oracleSandboxConditionSearchService.searchConditions(oracleHealthSandboxProfile);

        assertThat(result.outcome()).isEqualTo(FhirConditionSearchOutcome.AUTHENTICATION_REQUIRED);
        assertThat(result.toString()).doesNotContain("access_token");
        assertThat(result.toString()).doesNotContain("Condition/");
        assertThat(fhirService).isNotNull();
    }
}

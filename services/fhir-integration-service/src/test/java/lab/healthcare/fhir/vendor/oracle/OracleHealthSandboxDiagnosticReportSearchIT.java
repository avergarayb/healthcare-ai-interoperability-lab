package lab.healthcare.fhir.vendor.oracle;

import lab.healthcare.fhir.client.FhirService;
import lab.healthcare.fhir.routing.FhirDiagnosticReportSearchOutcome;
import lab.healthcare.fhir.routing.FhirDiagnosticReportSearchResult;
import lab.healthcare.fhir.server.FhirServerProfile;
import lab.healthcare.fhir.vendor.FhirVendor;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
class OracleHealthSandboxDiagnosticReportSearchIT {

    @Autowired
    private OracleSandboxDiagnosticReportSearchService oracleSandboxDiagnosticReportSearchService;

    @Autowired
    private OracleHealthIntegrationProfile oracleHealthSandboxProfile;

    @Autowired
    private FhirServerProfile activeFhirServerProfile;

    @Autowired
    private FhirService fhirService;

    @Test
    void defaultDisabledOracleDoesNotSearchDiagnosticReports() {
        assertThat(activeFhirServerProfile.name()).isEqualTo("local-hapi");
        assertThat(activeFhirServerProfile.vendor()).isEqualTo(FhirVendor.GENERIC);
        assertThat(oracleHealthSandboxProfile.enabled()).isFalse();
        assertThat(oracleHealthSandboxProfile.hasConfiguredPatientId()).isFalse();

        FhirDiagnosticReportSearchResult result =
                oracleSandboxDiagnosticReportSearchService.searchDiagnosticReports(oracleHealthSandboxProfile);

        assertThat(result.outcome()).isEqualTo(FhirDiagnosticReportSearchOutcome.AUTHENTICATION_REQUIRED);
        assertThat(result.toString()).doesNotContain("access_token");
        assertThat(result.toString()).doesNotContain("DiagnosticReport/");
        assertThat(fhirService).isNotNull();
    }
}

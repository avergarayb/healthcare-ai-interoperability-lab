package lab.healthcare.fhir.vendor.epic;

import lab.healthcare.fhir.routing.FhirDiagnosticReportSearchOutcome;
import lab.healthcare.fhir.routing.FhirDiagnosticReportSearchResult;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assumptions.assumeThat;

/**
 * Opt-in authenticated DiagnosticReport SEARCH_TYPE. Excluded from {@code -Pintegration}.
 * Maven cannot complete browser login, so a missing session token is
 * {@code AUTHENTICATION_REQUIRED}. A missing Patient ID is
 * {@code PATIENT_CONTEXT_NOT_CONFIGURED}. Do not fabricate credentials or IDs.
 * Run with {@code EPIC_SANDBOX_LIVE_IT=true}.
 */
@EnabledIfEnvironmentVariable(named = "EPIC_SANDBOX_LIVE_IT", matches = "true")
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
class EpicSandboxDiagnosticReportSearchLiveIT {

    @Autowired
    private EpicSandboxDiagnosticReportSearchService epicSandboxDiagnosticReportSearchService;

    @Autowired
    private EpicIntegrationProfile epicSandboxProfile;

    @Test
    void configuredSandboxDiagnosesDiagnosticReportSearchWithoutDumpingClinicalData() {
        assumeThat(epicSandboxProfile.enabled()).isTrue();
        assumeThat(epicSandboxProfile.fhirBaseUrl()).isNotBlank();

        FhirDiagnosticReportSearchResult result =
                epicSandboxDiagnosticReportSearchService.searchDiagnosticReports(epicSandboxProfile);

        assertThat(result.outcome()).isIn(
                FhirDiagnosticReportSearchOutcome.PATIENT_CONTEXT_NOT_CONFIGURED,
                FhirDiagnosticReportSearchOutcome.AUTHENTICATION_REQUIRED,
                FhirDiagnosticReportSearchOutcome.DIAGNOSTIC_REPORT_SEARCH_SUCCEEDED,
                FhirDiagnosticReportSearchOutcome.AUTHENTICATION_REJECTED,
                FhirDiagnosticReportSearchOutcome.AUTHORIZATION_DENIED,
                FhirDiagnosticReportSearchOutcome.CAPABILITY_UNSUPPORTED,
                FhirDiagnosticReportSearchOutcome.DEPENDENCY_FAILURE);
        assertThat(result.destination()).isEqualTo(EpicIntegrationProfile.SANDBOX_SERVER);
        assertThat(result.resourceType()).isEqualTo("DiagnosticReport");
        assertThat(result.toString()).doesNotContain("access_token");
        assertThat(result.toString()).doesNotContain("Bearer ");
        assertThat(result.toString()).doesNotContain("DiagnosticReport/");
        assertThat(result.detail()).doesNotContain("access_token");
        if (epicSandboxProfile.hasConfiguredPatientId()) {
            assertThat(result.toString()).doesNotContain(epicSandboxProfile.configuredPatientId());
        }
    }
}

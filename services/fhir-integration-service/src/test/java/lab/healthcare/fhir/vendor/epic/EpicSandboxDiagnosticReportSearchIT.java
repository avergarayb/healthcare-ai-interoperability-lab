package lab.healthcare.fhir.vendor.epic;

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
class EpicSandboxDiagnosticReportSearchIT {

    @Autowired
    private EpicSandboxDiagnosticReportSearchService epicSandboxDiagnosticReportSearchService;

    @Autowired
    private EpicIntegrationProfile epicSandboxProfile;

    @Autowired
    private FhirServerProfile activeFhirServerProfile;

    @Autowired
    private FhirService fhirService;

    @Test
    void defaultDisabledEpicDoesNotSearchDiagnosticReports() {
        assertThat(activeFhirServerProfile.name()).isEqualTo("local-hapi");
        assertThat(activeFhirServerProfile.vendor()).isEqualTo(FhirVendor.GENERIC);
        assertThat(epicSandboxProfile.enabled()).isFalse();
        assertThat(epicSandboxProfile.hasConfiguredPatientId()).isFalse();

        FhirDiagnosticReportSearchResult result =
                epicSandboxDiagnosticReportSearchService.searchDiagnosticReports(epicSandboxProfile);

        assertThat(result.outcome()).isEqualTo(FhirDiagnosticReportSearchOutcome.AUTHENTICATION_REQUIRED);
        assertThat(result.toString()).doesNotContain("access_token");
        assertThat(result.toString()).doesNotContain("DiagnosticReport/");
        assertThat(fhirService).isNotNull();
    }
}

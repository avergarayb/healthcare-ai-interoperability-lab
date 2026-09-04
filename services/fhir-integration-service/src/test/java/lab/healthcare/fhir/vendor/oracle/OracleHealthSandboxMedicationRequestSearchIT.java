package lab.healthcare.fhir.vendor.oracle;

import lab.healthcare.fhir.client.FhirService;
import lab.healthcare.fhir.routing.FhirMedicationRequestSearchOutcome;
import lab.healthcare.fhir.routing.FhirMedicationRequestSearchResult;
import lab.healthcare.fhir.server.FhirServerProfile;
import lab.healthcare.fhir.vendor.FhirVendor;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
class OracleHealthSandboxMedicationRequestSearchIT {

    @Autowired
    private OracleSandboxMedicationRequestSearchService oracleSandboxMedicationRequestSearchService;

    @Autowired
    private OracleHealthIntegrationProfile oracleHealthSandboxProfile;

    @Autowired
    private FhirServerProfile activeFhirServerProfile;

    @Autowired
    private FhirService fhirService;

    @Test
    void defaultDisabledOracleDoesNotSearchMedicationRequests() {
        assertThat(activeFhirServerProfile.name()).isEqualTo("local-hapi");
        assertThat(activeFhirServerProfile.vendor()).isEqualTo(FhirVendor.GENERIC);
        assertThat(oracleHealthSandboxProfile.enabled()).isFalse();
        assertThat(oracleHealthSandboxProfile.hasConfiguredPatientId()).isFalse();

        FhirMedicationRequestSearchResult result =
                oracleSandboxMedicationRequestSearchService.searchMedicationRequests(oracleHealthSandboxProfile);

        assertThat(result.outcome()).isEqualTo(FhirMedicationRequestSearchOutcome.AUTHENTICATION_REQUIRED);
        assertThat(result.toString()).doesNotContain("access_token");
        assertThat(result.toString()).doesNotContain("MedicationRequest/");
        assertThat(fhirService).isNotNull();
    }
}

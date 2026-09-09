package lab.healthcare.fhir.vendor.epic;

import lab.healthcare.fhir.routing.FhirObservationSearchOutcome;
import lab.healthcare.fhir.routing.FhirObservationSearchResult;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assumptions.assumeThat;

/**
 * Opt-in authenticated Observation SEARCH_TYPE. Excluded from {@code -Pintegration}.
 * Maven cannot complete browser login, so a missing session token is
 * {@code AUTHENTICATION_REQUIRED}. A missing Patient ID is
 * {@code PATIENT_CONTEXT_NOT_CONFIGURED}. Do not fabricate credentials or IDs.
 * Run with {@code EPIC_SANDBOX_LIVE_IT=true}.
 */
@EnabledIfEnvironmentVariable(named = "EPIC_SANDBOX_LIVE_IT", matches = "true")
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
class EpicSandboxObservationSearchLiveIT {

    @Autowired
    private EpicSandboxObservationSearchService epicSandboxObservationSearchService;

    @Autowired
    private EpicIntegrationProfile epicSandboxProfile;

    @Test
    void configuredSandboxDiagnosesObservationSearchWithoutDumpingClinicalData() {
        assumeThat(epicSandboxProfile.enabled()).isTrue();
        assumeThat(epicSandboxProfile.fhirBaseUrl()).isNotBlank();

        FhirObservationSearchResult result =
                epicSandboxObservationSearchService.searchObservations(epicSandboxProfile);

        assertThat(result.outcome()).isIn(
                FhirObservationSearchOutcome.PATIENT_CONTEXT_NOT_CONFIGURED,
                FhirObservationSearchOutcome.AUTHENTICATION_REQUIRED,
                FhirObservationSearchOutcome.OBSERVATION_SEARCH_SUCCEEDED,
                FhirObservationSearchOutcome.AUTHENTICATION_REJECTED,
                FhirObservationSearchOutcome.AUTHORIZATION_DENIED,
                FhirObservationSearchOutcome.CAPABILITY_UNSUPPORTED,
                FhirObservationSearchOutcome.DEPENDENCY_FAILURE);
        assertThat(result.destination()).isEqualTo(EpicIntegrationProfile.SANDBOX_SERVER);
        assertThat(result.resourceType()).isEqualTo("Observation");
        assertThat(result.toString()).doesNotContain("access_token");
        assertThat(result.toString()).doesNotContain("Bearer ");
        assertThat(result.toString()).doesNotContain("Observation/");
        assertThat(result.detail()).doesNotContain("access_token");
        if (epicSandboxProfile.hasConfiguredPatientId()) {
            assertThat(result.toString()).doesNotContain(epicSandboxProfile.configuredPatientId());
        }
    }
}

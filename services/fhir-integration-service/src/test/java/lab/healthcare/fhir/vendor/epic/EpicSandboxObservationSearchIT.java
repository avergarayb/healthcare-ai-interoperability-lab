package lab.healthcare.fhir.vendor.epic;

import lab.healthcare.fhir.client.FhirService;
import lab.healthcare.fhir.routing.FhirObservationSearchOutcome;
import lab.healthcare.fhir.routing.FhirObservationSearchResult;
import lab.healthcare.fhir.server.FhirServerProfile;
import lab.healthcare.fhir.vendor.FhirVendor;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
class EpicSandboxObservationSearchIT {

    @Autowired
    private EpicSandboxObservationSearchService epicSandboxObservationSearchService;

    @Autowired
    private EpicIntegrationProfile epicSandboxProfile;

    @Autowired
    private FhirServerProfile activeFhirServerProfile;

    @Autowired
    private FhirService fhirService;

    @Test
    void defaultDisabledEpicDoesNotSearchObservations() {
        assertThat(activeFhirServerProfile.name()).isEqualTo("local-hapi");
        assertThat(activeFhirServerProfile.vendor()).isEqualTo(FhirVendor.GENERIC);
        assertThat(epicSandboxProfile.enabled()).isFalse();
        assertThat(epicSandboxProfile.hasConfiguredPatientId()).isFalse();

        FhirObservationSearchResult result =
                epicSandboxObservationSearchService.searchObservations(epicSandboxProfile);

        assertThat(result.outcome()).isEqualTo(FhirObservationSearchOutcome.AUTHENTICATION_REQUIRED);
        assertThat(result.toString()).doesNotContain("access_token");
        assertThat(result.toString()).doesNotContain("Observation/");
        assertThat(fhirService).isNotNull();
    }
}

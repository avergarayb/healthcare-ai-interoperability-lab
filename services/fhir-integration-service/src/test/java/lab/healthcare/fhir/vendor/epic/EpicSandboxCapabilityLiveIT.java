package lab.healthcare.fhir.vendor.epic;

import lab.healthcare.fhir.capability.FhirServerCapabilities;

import org.junit.jupiter.api.Test;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assumptions.assumeThat;

/**
 * Opt-in live CapabilityStatement fetch. Excluded from {@code -Pintegration}.
 * {@code GET /metadata} is attempted without an access token. Run with
 * {@code mvn verify -Pepic-live} and {@code EPIC_SANDBOX_LIVE_IT=true}.
 */
@EnabledIfEnvironmentVariable(named = "EPIC_SANDBOX_LIVE_IT", matches = "true")
@SpringBootTest(
        webEnvironment = SpringBootTest.WebEnvironment.NONE,
        properties = {
            "EPIC_SANDBOX_ENABLED=true",
            "EPIC_SANDBOX_CLIENT_ID=live-it-placeholder",
            "EPIC_SANDBOX_REDIRECT_URI=http://127.0.0.1:8081/smart/callback",
            "EPIC_SANDBOX_SCOPE=openid fhirUser user/*.read",
            "EPIC_SANDBOX_SMART_CONFIGURATION_URL=http://127.0.0.1/does-not-contact-epic/.well-known/smart-configuration"
        })
class EpicSandboxCapabilityLiveIT {

    private static final Logger log = LoggerFactory.getLogger(EpicSandboxCapabilityLiveIT.class);

    @Autowired
    private EpicSandboxCapabilityDiscoveryService epicSandboxCapabilityDiscoveryService;

    @Autowired
    private EpicIntegrationProfile epicSandboxProfile;

    @Test
    void configuredSandboxMetadataIsDiscoveredWithoutReadingPatient() {
        assumeThat(epicSandboxProfile.enabled()).isTrue();
        assumeThat(epicSandboxProfile.fhirBaseUrl()).isNotBlank();

        FhirServerCapabilities capabilities = epicSandboxCapabilityDiscoveryService.discover(epicSandboxProfile);

        log.info(
                "Epic capability discovery status=SUCCESS httpStatus=200 fhirVersion={} resourceTypes={}",
                capabilities.fhirVersion(),
                capabilities.resources().size());

        assertThat(capabilities.destination()).isEqualTo(EpicIntegrationProfile.SANDBOX_SERVER);
        assertThat(capabilities.fhirVersion()).isNotBlank();
        assertThat(capabilities.resources()).isNotEmpty();
        assertThat(EpicKnownApiSurface.assumesEveryR4Resource()).isFalse();
        assertThat(capabilities.toString()).doesNotContain("access_token");
        assertThat(capabilities.toString()).doesNotContain("Patient/");
        assertThat(epicSandboxProfile.toUnauthenticatedMetadataProfile().authentication().requiresBearerToken())
                .isFalse();
    }
}

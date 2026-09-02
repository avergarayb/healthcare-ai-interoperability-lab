package lab.healthcare.fhir.vendor.oracle;

import lab.healthcare.fhir.capability.FhirInteraction;
import lab.healthcare.fhir.capability.FhirServerCapabilities;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assumptions.assumeThat;

/**
 * Opt-in live CapabilityStatement fetch. Excluded from {@code -Pintegration}.
 * {@code GET /metadata} is public on the Oracle Code sandbox; no access token is
 * used. Run with {@code mvn verify -Poracle-live} and {@code ORACLE_HEALTH_LIVE_IT=true}.
 */
@EnabledIfEnvironmentVariable(named = "ORACLE_HEALTH_LIVE_IT", matches = "true")
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
class OracleHealthSandboxCapabilityLiveIT {

    @Autowired
    private OracleSandboxCapabilityDiscoveryService oracleSandboxCapabilityDiscoveryService;

    @Autowired
    private OracleHealthIntegrationProfile oracleHealthSandboxProfile;

    @Test
    void configuredSandboxMetadataIsDiscoveredWithoutReadingPatient() {
        assumeThat(oracleHealthSandboxProfile.enabled()).isTrue();
        assumeThat(oracleHealthSandboxProfile.fhirBaseUrl()).isNotBlank();

        OracleSandboxReadiness readiness =
                oracleSandboxCapabilityDiscoveryService.inspect(oracleHealthSandboxProfile);
        assertThat(readiness.state()).isEqualTo(OracleSandboxReadinessState.READY_FOR_CONNECTIVITY_CHECK);

        FhirServerCapabilities capabilities =
                oracleSandboxCapabilityDiscoveryService.discover(oracleHealthSandboxProfile);

        assertThat(capabilities.destination()).isEqualTo(OracleHealthIntegrationProfile.SANDBOX_SERVER);
        assertThat(capabilities.fhirVersion()).isEqualTo("4.0.1");
        assertThat(capabilities.implementationUrl()).isEqualTo(oracleHealthSandboxProfile.fhirBaseUrl());
        assertThat(capabilities.supportsResource("Patient")).isTrue();
        assertThat(capabilities.supportsResource("Observation")).isTrue();
        assertThat(capabilities.supports("Patient", FhirInteraction.READ)).isTrue();
        assertThat(capabilities.supports("Patient", FhirInteraction.SEARCH_TYPE)).isTrue();
        assertThat(capabilities.supports("Patient", FhirInteraction.CREATE)).isTrue();
        assertThat(capabilities.supports("Patient", FhirInteraction.UPDATE)).isFalse();
        assertThat(capabilities.supports("Patient", FhirInteraction.DELETE)).isFalse();
        assertThat(capabilities.supportsResource("Medication")).isFalse();
        assertThat(capabilities.supportsResource("Claim")).isFalse();
        assertThat(OracleHealthKnownApiSurface.assumesEveryR4Resource()).isFalse();
        assertThat(capabilities.toString()).doesNotContain("access_token");
        assertThat(capabilities.toString()).doesNotContain("Patient/");
        assertThat(oracleHealthSandboxProfile.toUnauthenticatedMetadataProfile().authentication().requiresBearerToken())
                .isFalse();
    }
}

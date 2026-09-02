package lab.healthcare.fhir.vendor.oracle;

import lab.healthcare.fhir.auth.FhirAuthenticationSettings;
import lab.healthcare.fhir.auth.FhirAuthenticationType;
import lab.healthcare.fhir.server.FhirServerProfile;
import lab.healthcare.fhir.server.FhirServersProperties;
import lab.healthcare.fhir.vendor.FhirVendor;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class OracleHealthIntegrationProfileTest {

    static final String SYNTHETIC_BASE = "http://127.0.0.1/oracle-health-sandbox";

    @Test
    void mapsVendorEnvironmentFhirVersionLaunchAuthScopesAndAud() {
        OracleHealthIntegrationProfile profile = completePublicPkce();

        assertThat(profile.vendor()).isEqualTo(FhirVendor.ORACLE_HEALTH);
        assertThat(profile.environment()).isEqualTo(OracleHealthEnvironment.SANDBOX);
        assertThat(profile.fhirVersion()).isEqualTo("R4");
        assertThat(profile.launchMode()).isEqualTo(OracleHealthLaunchMode.STANDALONE);
        assertThat(profile.clientAuthentication()).isEqualTo(OracleHealthClientAuthentication.PUBLIC_PKCE);
        assertThat(profile.requestedScopes()).isEqualTo("patient/Patient.read");
        assertThat(profile.aud()).isEqualTo(SYNTHETIC_BASE);
        assertThat(profile.fhirBaseUrl()).isEqualTo(SYNTHETIC_BASE);
        assertThat(profile.userContext()).isEqualTo(OracleHealthUserContext.PATIENT);
        assertThat(profile.readiness()).isEqualTo(OracleHealthReadinessState.READY_FOR_SANDBOX);
        assertThat(profile.capabilities().supportsPkceS256()).isTrue();
        assertThat(profile.capabilities().supportsStandaloneLaunch()).isTrue();
        assertThat(profile.capabilities().supportsEhrLaunchReadiness()).isFalse();
        assertThat(profile.toString()).doesNotContain("client_secret");
        assertThat(profile.toString()).doesNotContain("access_token");
        assertThat(OracleHealthKnownApiSurface.assumesEveryR4Resource()).isFalse();
        assertThat(profile.toUnauthenticatedMetadataProfile().authentication().requiresBearerToken()).isFalse();
        assertThat(profile.toUnauthenticatedMetadataProfile().baseUrl()).isEqualTo(SYNTHETIC_BASE);
        assertThat(profile.toUnauthenticatedMetadataProfile().authentication().type())
                .isEqualTo(FhirAuthenticationType.NONE);
    }

    @Test
    void productionEnvironmentIsSmartCompatibleNotSandboxReady() {
        OracleHealthIntegrationProfile profile = OracleHealthIntegrationProfile.from(
                oracleServer(false, smartAuth()),
                new FhirServersProperties.VendorIntegrationSettings(
                        "PRODUCTION", "STANDALONE", "PATIENT", "PUBLIC_PKCE"));

        assertThat(profile.environment()).isEqualTo(OracleHealthEnvironment.PRODUCTION);
        assertThat(profile.readiness()).isEqualTo(OracleHealthReadinessState.SMART_COMPATIBLE);
    }

    @Test
    void privateKeyJwtIsConfiguredButNotRuntimeSmartCompatible() {
        OracleHealthIntegrationProfile profile = OracleHealthIntegrationProfile.from(
                oracleServer(false, smartAuth()),
                new FhirServersProperties.VendorIntegrationSettings(
                        "SANDBOX", "STANDALONE", "PATIENT", "PRIVATE_KEY_JWT"));

        assertThat(profile.clientAuthentication()).isEqualTo(OracleHealthClientAuthentication.PRIVATE_KEY_JWT);
        assertThat(profile.clientAuthentication().runtimeSupported()).isFalse();
        assertThat(profile.capabilities().runtimeSupportsClientAuthentication()).isFalse();
        assertThat(profile.readiness()).isEqualTo(OracleHealthReadinessState.CONFIGURED);
    }

    static OracleHealthIntegrationProfile completePublicPkce() {
        return OracleHealthIntegrationProfile.from(
                oracleServer(false, smartAuth()),
                new FhirServersProperties.VendorIntegrationSettings(
                        "SANDBOX", "STANDALONE", "PATIENT", "PUBLIC_PKCE"));
    }

    static OracleHealthIntegrationProfile completePublicPkceEnabled() {
        return OracleHealthIntegrationProfile.from(
                oracleServer(true, smartAuth()),
                new FhirServersProperties.VendorIntegrationSettings(
                        "SANDBOX", "STANDALONE", "PATIENT", "PUBLIC_PKCE"));
    }

    static FhirServerProfile oracleServer(boolean enabled, FhirAuthenticationSettings authentication) {
        return new FhirServerProfile(
                OracleHealthIntegrationProfile.SANDBOX_SERVER,
                SYNTHETIC_BASE,
                "R4",
                enabled,
                FhirVendor.ORACLE_HEALTH,
                authentication);
    }

    static FhirAuthenticationSettings smartAuth() {
        return new FhirAuthenticationSettings(
                FhirAuthenticationType.SMART_AUTHORIZATION_CODE,
                null,
                "lab-oracle-placeholder",
                "",
                "http://127.0.0.1/does-not-contact-oracle/.well-known/smart-configuration",
                "http://127.0.0.1:8081/smart/callback",
                "patient/Patient.read",
                SYNTHETIC_BASE);
    }
}

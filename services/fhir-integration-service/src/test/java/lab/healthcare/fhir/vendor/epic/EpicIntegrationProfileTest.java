package lab.healthcare.fhir.vendor.epic;

import lab.healthcare.fhir.auth.FhirAuthenticationSettings;
import lab.healthcare.fhir.auth.FhirAuthenticationType;
import lab.healthcare.fhir.server.FhirServerProfile;
import lab.healthcare.fhir.server.FhirServersProperties;
import lab.healthcare.fhir.vendor.FhirVendor;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class EpicIntegrationProfileTest {

    @Test
    void mapsVendorEnvironmentFhirVersionLaunchAuthScopesAndAud() {
        EpicIntegrationProfile profile = completePublicPkce();

        assertThat(profile.vendor()).isEqualTo(FhirVendor.EPIC);
        assertThat(profile.environment()).isEqualTo(EpicEnvironment.SANDBOX);
        assertThat(profile.fhirVersion()).isEqualTo("R4");
        assertThat(profile.launchMode()).isEqualTo(EpicLaunchMode.STANDALONE);
        assertThat(profile.clientAuthentication()).isEqualTo(EpicClientAuthentication.PUBLIC_PKCE);
        assertThat(profile.requestedScopes()).isEqualTo("patient/Patient.read");
        assertThat(profile.aud()).isEqualTo(EpicSandboxEndpoints.FHIR_R4_BASE);
        assertThat(profile.userContext()).isEqualTo(EpicUserContext.PATIENT);
        assertThat(profile.readiness()).isEqualTo(EpicReadinessState.READY_FOR_SANDBOX);
        assertThat(profile.capabilities().supportsPkceS256()).isTrue();
        assertThat(profile.capabilities().supportsEhrLaunchReadiness()).isFalse();
        assertThat(profile.capabilities().supportsPersistentAccessReadiness()).isFalse();
        assertThat(profile.toString()).doesNotContain("client_secret");
        assertThat(profile.toString()).doesNotContain("access_token");
        assertThat(profile.toString()).doesNotContain("private_key");
        assertThat(EpicKnownApiSurface.assumesEveryR4Resource()).isFalse();
    }

    @Test
    void privateKeyJwtIsConfiguredButNotRuntimeSmartCompatible() {
        EpicIntegrationProfile profile = EpicIntegrationProfile.from(
                epicServer(false, smartAuth()),
                new FhirServersProperties.VendorIntegrationSettings(
                        "SANDBOX", "STANDALONE", "PATIENT", "PRIVATE_KEY_JWT"));

        assertThat(profile.clientAuthentication()).isEqualTo(EpicClientAuthentication.PRIVATE_KEY_JWT);
        assertThat(profile.clientAuthentication().runtimeSupported()).isFalse();
        assertThat(profile.capabilities().runtimeSupportsClientAuthentication()).isFalse();
        assertThat(profile.readiness()).isEqualTo(EpicReadinessState.CONFIGURED);
    }

    static EpicIntegrationProfile completePublicPkce() {
        return EpicIntegrationProfile.from(
                epicServer(false, smartAuth()),
                new FhirServersProperties.VendorIntegrationSettings(
                        "SANDBOX", "STANDALONE", "PATIENT", "PUBLIC_PKCE"));
    }

    static FhirServerProfile epicServer(boolean enabled, FhirAuthenticationSettings authentication) {
        return new FhirServerProfile(
                EpicIntegrationProfile.SANDBOX_SERVER,
                EpicSandboxEndpoints.FHIR_R4_BASE,
                "R4",
                enabled,
                FhirVendor.EPIC,
                authentication);
    }

    static FhirAuthenticationSettings smartAuth() {
        return new FhirAuthenticationSettings(
                FhirAuthenticationType.SMART_AUTHORIZATION_CODE,
                null,
                "lab-epic-placeholder",
                "",
                "http://127.0.0.1/does-not-contact-epic/.well-known/smart-configuration",
                "http://127.0.0.1:8081/smart/callback",
                "patient/Patient.read",
                EpicSandboxEndpoints.FHIR_R4_BASE);
    }
}

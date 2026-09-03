package lab.healthcare.fhir.vendor.epic;

import lab.healthcare.fhir.auth.FhirAuthenticationSettings;
import lab.healthcare.fhir.auth.FhirAuthenticationType;
import lab.healthcare.fhir.server.FhirServerProfile;
import lab.healthcare.fhir.server.FhirServersProperties;
import lab.healthcare.fhir.vendor.FhirVendor;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class EpicProfileValidatorTest {

    private final EpicProfileValidator validator = new EpicProfileValidator();

    @Test
    void acceptsCompleteSandboxProfileForPublicPkce() {
        assertThatCode(() -> validator.validate(EpicIntegrationProfileTest.completePublicPkce()))
                .doesNotThrowAnyException();
        assertThatCode(() -> validator.validateForRuntime(EpicIntegrationProfileTest.completePublicPkce()))
                .doesNotThrowAnyException();
    }

    @Test
    void rejectsWrongVendor() {
        FhirServerProfile generic = new FhirServerProfile(
                "epic-sandbox",
                EpicSandboxEndpoints.FHIR_R4_BASE,
                "R4",
                false,
                FhirVendor.GENERIC,
                EpicIntegrationProfileTest.smartAuth());
        EpicIntegrationProfile profile = EpicIntegrationProfile.from(generic, null);

        assertThatThrownBy(() -> validator.validate(profile))
                .isInstanceOf(EpicProfileException.class)
                .hasMessageContaining("EPIC")
                .hasMessageNotContaining("client_secret")
                .hasMessageNotContaining("access_token");
    }

    @Test
    void rejectsUnsupportedFhirVersion() {
        FhirServerProfile r5 = new FhirServerProfile(
                "epic-sandbox",
                EpicSandboxEndpoints.FHIR_R4_BASE,
                "R5",
                false,
                FhirVendor.EPIC,
                EpicIntegrationProfileTest.smartAuth());

        assertThatThrownBy(() -> validator.validate(EpicIntegrationProfile.from(r5, null)))
                .isInstanceOf(EpicProfileException.class)
                .hasMessageContaining("R4");
    }

    @Test
    void rejectsMissingBaseUrl() {
        FhirServerProfile missingBase = new FhirServerProfile(
                "epic-sandbox",
                "  ",
                "R4",
                false,
                FhirVendor.EPIC,
                EpicIntegrationProfileTest.smartAuth());

        assertThatThrownBy(() -> validator.validate(EpicIntegrationProfile.from(missingBase, null)))
                .isInstanceOf(EpicProfileException.class)
                .hasMessageContaining("base URL");
    }

    @Test
    void rejectsEnabledProfileMissingClientId() {
        FhirAuthenticationSettings auth = new FhirAuthenticationSettings(
                FhirAuthenticationType.SMART_AUTHORIZATION_CODE,
                null,
                "",
                "",
                "http://127.0.0.1/does-not-contact-epic/.well-known/smart-configuration",
                "http://127.0.0.1:8081/smart/callback",
                "patient/Patient.read",
                EpicSandboxEndpoints.FHIR_R4_BASE);
        EpicIntegrationProfile profile = EpicIntegrationProfile.from(
                EpicIntegrationProfileTest.epicServer(true, auth), null);

        assertThatThrownBy(() -> validator.validate(profile))
                .isInstanceOf(EpicProfileException.class)
                .hasMessageContaining("client ID");
    }

    @Test
    void rejectsEnabledAuthorizationCodeProfileMissingRedirectUri() {
        FhirAuthenticationSettings auth = new FhirAuthenticationSettings(
                FhirAuthenticationType.SMART_AUTHORIZATION_CODE,
                null,
                "lab-epic-placeholder",
                "",
                "http://127.0.0.1/does-not-contact-epic/.well-known/smart-configuration",
                "",
                "patient/Patient.read",
                EpicSandboxEndpoints.FHIR_R4_BASE);
        EpicIntegrationProfile profile = EpicIntegrationProfile.from(
                EpicIntegrationProfileTest.epicServer(true, auth), null);

        assertThatThrownBy(() -> validator.validate(profile))
                .isInstanceOf(EpicProfileException.class)
                .hasMessageContaining("redirect URI");
    }

    @Test
    void rejectsMissingAud() {
        FhirAuthenticationSettings auth = new FhirAuthenticationSettings(
                FhirAuthenticationType.SMART_AUTHORIZATION_CODE,
                null,
                "lab-epic-placeholder",
                "",
                "http://127.0.0.1/does-not-contact-epic/.well-known/smart-configuration",
                "http://127.0.0.1:8081/smart/callback",
                "patient/Patient.read",
                "");
        EpicIntegrationProfile profile = EpicIntegrationProfile.from(
                EpicIntegrationProfileTest.epicServer(false, auth), null);

        assertThatThrownBy(() -> validator.validate(profile))
                .isInstanceOf(EpicProfileException.class)
                .hasMessageContaining("aud");
    }

    @Test
    void rejectsUnsupportedRuntimeAuthWhenRequired() {
        EpicIntegrationProfile profile = EpicIntegrationProfile.from(
                EpicIntegrationProfileTest.epicServer(false, EpicIntegrationProfileTest.smartAuth()),
                FhirServersProperties.VendorIntegrationSettings.of(
                        "SANDBOX", "STANDALONE", "PATIENT", "PRIVATE_KEY_JWT"));

        assertThatCode(() -> validator.validate(profile)).doesNotThrowAnyException();
        assertThatThrownBy(() -> validator.validateForRuntime(profile))
                .isInstanceOf(EpicProfileException.class)
                .hasMessageContaining("PRIVATE_KEY_JWT")
                .hasMessageContaining("not supported");
    }

    @Test
    void disabledIncompleteProfileDoesNotRequireClientId() {
        FhirAuthenticationSettings auth = new FhirAuthenticationSettings(
                FhirAuthenticationType.SMART_AUTHORIZATION_CODE,
                null,
                "",
                "",
                null,
                "",
                "",
                EpicSandboxEndpoints.FHIR_R4_BASE);
        EpicIntegrationProfile profile = EpicIntegrationProfile.from(
                EpicIntegrationProfileTest.epicServer(false, auth), null);

        assertThat(profile.readiness()).isEqualTo(EpicReadinessState.NOT_CONFIGURED);
        assertThatCode(() -> validator.validate(profile)).doesNotThrowAnyException();
    }
}

package lab.healthcare.fhir.vendor.oracle;

import lab.healthcare.fhir.auth.FhirAuthenticationSettings;
import lab.healthcare.fhir.auth.FhirAuthenticationType;
import lab.healthcare.fhir.server.FhirServerProfile;
import lab.healthcare.fhir.server.FhirServersProperties;
import lab.healthcare.fhir.vendor.FhirVendor;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class OracleHealthProfileValidatorTest {

    private final OracleHealthProfileValidator validator = new OracleHealthProfileValidator();

    @Test
    void acceptsCompleteSandboxProfileForPublicPkce() {
        assertThatCode(() -> validator.validate(OracleHealthIntegrationProfileTest.completePublicPkce()))
                .doesNotThrowAnyException();
        assertThatCode(() -> validator.validateForRuntime(OracleHealthIntegrationProfileTest.completePublicPkce()))
                .doesNotThrowAnyException();
    }

    @Test
    void acceptsDisabledProfileWithEmptyRegistrationValues() {
        FhirAuthenticationSettings auth = new FhirAuthenticationSettings(
                FhirAuthenticationType.SMART_AUTHORIZATION_CODE,
                null,
                "",
                "",
                null,
                "",
                "",
                "");
        OracleHealthIntegrationProfile profile = OracleHealthIntegrationProfile.from(
                new FhirServerProfile(
                        OracleHealthIntegrationProfile.SANDBOX_SERVER,
                        "",
                        "R4",
                        false,
                        FhirVendor.ORACLE_HEALTH,
                        auth),
                null);

        assertThat(profile.readiness()).isEqualTo(OracleHealthReadinessState.NOT_CONFIGURED);
        assertThatCode(() -> validator.validate(profile)).doesNotThrowAnyException();
    }

    @Test
    void rejectsWrongVendor() {
        FhirServerProfile generic = new FhirServerProfile(
                "oracle-health-sandbox",
                OracleHealthIntegrationProfileTest.SYNTHETIC_BASE,
                "R4",
                false,
                FhirVendor.GENERIC,
                OracleHealthIntegrationProfileTest.smartAuth());

        assertThatThrownBy(() -> validator.validate(OracleHealthIntegrationProfile.from(generic, null)))
                .isInstanceOf(OracleHealthProfileException.class)
                .hasMessageContaining("ORACLE_HEALTH")
                .hasMessageNotContaining("client_secret")
                .hasMessageNotContaining("access_token");
    }

    @Test
    void rejectsUnsupportedFhirVersion() {
        FhirServerProfile r5 = new FhirServerProfile(
                "oracle-health-sandbox",
                OracleHealthIntegrationProfileTest.SYNTHETIC_BASE,
                "R5",
                false,
                FhirVendor.ORACLE_HEALTH,
                OracleHealthIntegrationProfileTest.smartAuth());

        assertThatThrownBy(() -> validator.validate(OracleHealthIntegrationProfile.from(r5, null)))
                .isInstanceOf(OracleHealthProfileException.class)
                .hasMessageContaining("R4");
    }

    @Test
    void rejectsEnabledProfileMissingClientId() {
        FhirAuthenticationSettings auth = new FhirAuthenticationSettings(
                FhirAuthenticationType.SMART_AUTHORIZATION_CODE,
                null,
                "",
                "",
                "http://127.0.0.1/does-not-contact-oracle/.well-known/smart-configuration",
                "http://127.0.0.1:8081/smart/callback",
                "patient/Patient.read",
                OracleHealthIntegrationProfileTest.SYNTHETIC_BASE);
        OracleHealthIntegrationProfile profile = OracleHealthIntegrationProfile.from(
                OracleHealthIntegrationProfileTest.oracleServer(true, auth), null);

        assertThatThrownBy(() -> validator.validate(profile))
                .isInstanceOf(OracleHealthProfileException.class)
                .hasMessageContaining("client ID");
    }

    @Test
    void rejectsEnabledProfileMissingBaseUrl() {
        FhirServerProfile missingBase = new FhirServerProfile(
                OracleHealthIntegrationProfile.SANDBOX_SERVER,
                "",
                "R4",
                true,
                FhirVendor.ORACLE_HEALTH,
                OracleHealthIntegrationProfileTest.smartAuth());
        OracleHealthIntegrationProfile profile = OracleHealthIntegrationProfile.from(missingBase, null);

        assertThatThrownBy(() -> validator.validate(profile))
                .isInstanceOf(OracleHealthProfileException.class)
                .hasMessageContaining("base URL");
    }

    @Test
    void rejectsUnsupportedRuntimeAuthWhenRequired() {
        OracleHealthIntegrationProfile profile = OracleHealthIntegrationProfile.from(
                OracleHealthIntegrationProfileTest.oracleServer(
                        false, OracleHealthIntegrationProfileTest.smartAuth()),
                new FhirServersProperties.VendorIntegrationSettings(
                        "SANDBOX", "STANDALONE", "PATIENT", "PRIVATE_KEY_JWT"));

        assertThatCode(() -> validator.validate(profile)).doesNotThrowAnyException();
        assertThatThrownBy(() -> validator.validateForRuntime(profile))
                .isInstanceOf(OracleHealthProfileException.class)
                .hasMessageContaining("PRIVATE_KEY_JWT")
                .hasMessageContaining("not supported");
    }
}

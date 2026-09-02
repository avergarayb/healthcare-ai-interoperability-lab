package lab.healthcare.fhir.vendor.oracle;

import lab.healthcare.fhir.auth.FhirAuthenticationSettings;
import lab.healthcare.fhir.auth.FhirAuthenticationType;
import lab.healthcare.fhir.server.FhirServerProfile;
import lab.healthcare.fhir.server.FhirServersProperties;
import lab.healthcare.fhir.vendor.FhirVendor;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class OracleSandboxProfileValidatorTest {

    private final OracleSandboxProfileValidator validator = new OracleSandboxProfileValidator();

    @Test
    void disabledProfileDoesNotRequireOracleCredentials() {
        assertThatCode(() -> validator.validateDisabledAllowed(disabledEmpty()))
                .doesNotThrowAnyException();
        assertThatCode(() -> validator.validateForConnectivity(disabledEmpty())).doesNotThrowAnyException();
    }

    @Test
    void enabledCompleteSandboxIsValidForConnectivity() {
        assertThatCode(() -> validator.validateForConnectivity(
                        OracleHealthIntegrationProfileTest.completePublicPkceEnabled()))
                .doesNotThrowAnyException();
        assertThatCode(() -> validator.validateForAuthorization(
                        OracleHealthIntegrationProfileTest.completePublicPkceEnabled()))
                .doesNotThrowAnyException();
    }

    @Test
    void disabledProfileIsRejectedForAuthorization() {
        assertThatThrownBy(() -> validator.validateForAuthorization(disabledEmpty()))
                .isInstanceOf(OracleHealthProfileException.class)
                .hasMessageContaining("disabled");
    }

    @Test
    void enabledMissingBaseUrlFailsExplicitly() {
        FhirServerProfile missingBase = new FhirServerProfile(
                OracleHealthIntegrationProfile.SANDBOX_SERVER,
                "",
                "R4",
                true,
                FhirVendor.ORACLE_HEALTH,
                OracleHealthIntegrationProfileTest.smartAuth());

        assertThatThrownBy(() -> validator.validateForConnectivity(
                        OracleHealthIntegrationProfile.from(missingBase, null)))
                .isInstanceOf(OracleHealthProfileException.class)
                .hasMessageContaining("base URL")
                .hasMessageNotContaining("client_secret")
                .hasMessageNotContaining("access_token");
    }

    @Test
    void enabledMissingClientIdFailsExplicitly() {
        FhirAuthenticationSettings auth = new FhirAuthenticationSettings(
                FhirAuthenticationType.SMART_AUTHORIZATION_CODE,
                null,
                "",
                "",
                "http://127.0.0.1/does-not-contact-oracle/.well-known/smart-configuration",
                "http://127.0.0.1:8081/smart/callback",
                "patient/Patient.read",
                OracleHealthIntegrationProfileTest.SYNTHETIC_BASE);

        assertThatThrownBy(() -> validator.validateForConnectivity(
                        OracleHealthIntegrationProfile.from(
                                OracleHealthIntegrationProfileTest.oracleServer(true, auth), null)))
                .isInstanceOf(OracleHealthProfileException.class)
                .hasMessageContaining("client ID");
    }

    @Test
    void malformedUriFailsWithoutEchoingCredentials() {
        FhirAuthenticationSettings auth = new FhirAuthenticationSettings(
                FhirAuthenticationType.SMART_AUTHORIZATION_CODE,
                null,
                "lab-oracle-placeholder",
                "",
                "http://127.0.0.1/does-not-contact-oracle/.well-known/smart-configuration",
                "http://127.0.0.1:8081/smart/callback",
                "patient/Patient.read",
                OracleHealthIntegrationProfileTest.SYNTHETIC_BASE);
        FhirServerProfile server = new FhirServerProfile(
                OracleHealthIntegrationProfile.SANDBOX_SERVER,
                "not a uri",
                "R4",
                true,
                FhirVendor.ORACLE_HEALTH,
                auth);

        assertThatThrownBy(() -> validator.validateForConnectivity(OracleHealthIntegrationProfile.from(server, null)))
                .isInstanceOf(OracleHealthProfileException.class)
                .hasMessageContaining("URI")
                .hasMessageNotContaining("client_secret");
    }

    @Test
    void uriWithUserInfoIsRejected() {
        FhirServerProfile server = new FhirServerProfile(
                OracleHealthIntegrationProfile.SANDBOX_SERVER,
                "http://user:super-secret@127.0.0.1/fhir",
                "R4",
                true,
                FhirVendor.ORACLE_HEALTH,
                OracleHealthIntegrationProfileTest.smartAuth());

        assertThatThrownBy(() -> validator.validateForConnectivity(OracleHealthIntegrationProfile.from(server, null)))
                .isInstanceOf(OracleHealthProfileException.class)
                .hasMessageContaining("credentials")
                .hasMessageNotContaining("super-secret");
    }

    @Test
    void unsupportedRuntimeAuthIsInvalidForConnectivity() {
        OracleHealthIntegrationProfile profile = OracleHealthIntegrationProfile.from(
                OracleHealthIntegrationProfileTest.oracleServer(true, OracleHealthIntegrationProfileTest.smartAuth()),
                new FhirServersProperties.VendorIntegrationSettings(
                        "SANDBOX", "STANDALONE", "PATIENT", "PRIVATE_KEY_JWT"));

        assertThatThrownBy(() -> validator.validateForConnectivity(profile))
                .isInstanceOf(OracleHealthProfileException.class)
                .hasMessageContaining("PRIVATE_KEY_JWT");
    }

    private static OracleHealthIntegrationProfile disabledEmpty() {
        FhirAuthenticationSettings auth = new FhirAuthenticationSettings(
                FhirAuthenticationType.SMART_AUTHORIZATION_CODE,
                null,
                "",
                "",
                null,
                "",
                "",
                "");
        return OracleHealthIntegrationProfile.from(
                new FhirServerProfile(
                        OracleHealthIntegrationProfile.SANDBOX_SERVER,
                        "",
                        "R4",
                        false,
                        FhirVendor.ORACLE_HEALTH,
                        auth),
                null);
    }
}

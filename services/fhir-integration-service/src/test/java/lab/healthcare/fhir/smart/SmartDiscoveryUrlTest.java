package lab.healthcare.fhir.smart;

import lab.healthcare.fhir.auth.FhirAuthenticationSettings;
import lab.healthcare.fhir.auth.FhirAuthenticationType;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class SmartDiscoveryUrlTest {

    @Test
    void usesConfiguredProfileUrlWithoutVendorConcatenation() {
        FhirAuthenticationSettings authentication = new FhirAuthenticationSettings(
                FhirAuthenticationType.SMART_AUTHORIZATION_CODE,
                null,
                "lab-smart-app",
                "",
                "http://localhost:8180/fhir/.well-known/smart-configuration",
                "http://127.0.0.1:8081/smart/callback",
                "patient/Patient.read",
                "http://localhost:8180/fhir");

        assertThat(SmartDiscoveryUrl.from(authentication))
                .isEqualTo("http://localhost:8180/fhir/.well-known/smart-configuration");
    }

    @Test
    void rejectsClientCredentialsSettings() {
        assertThatThrownBy(() -> SmartDiscoveryUrl.from(FhirAuthenticationSettings.none()))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("SMART");
    }
}

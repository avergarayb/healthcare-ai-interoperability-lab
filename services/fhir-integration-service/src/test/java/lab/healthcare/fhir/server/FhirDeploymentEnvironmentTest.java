package lab.healthcare.fhir.server;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class FhirDeploymentEnvironmentTest {

    @Test
    void parsesKnownEnvironmentsWithoutDefaultingSandboxForBlank() {
        assertThat(FhirDeploymentEnvironment.fromConfiguration(null)).isEqualTo(FhirDeploymentEnvironment.LOCAL);
        assertThat(FhirDeploymentEnvironment.fromConfiguration(" ")).isEqualTo(FhirDeploymentEnvironment.LOCAL);
        assertThat(FhirDeploymentEnvironment.fromConfiguration("synthetic"))
                .isEqualTo(FhirDeploymentEnvironment.SYNTHETIC);
        assertThat(FhirDeploymentEnvironment.fromConfiguration("SANDBOX"))
                .isEqualTo(FhirDeploymentEnvironment.SANDBOX);
        assertThat(FhirDeploymentEnvironment.fromConfiguration("PRODUCTION"))
                .isEqualTo(FhirDeploymentEnvironment.PRODUCTION);
    }
}

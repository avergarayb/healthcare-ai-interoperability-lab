package lab.healthcare.fhir.client;

import ca.uhn.fhir.context.FhirContext;
import ca.uhn.fhir.context.FhirVersionEnum;
import ca.uhn.fhir.rest.client.api.IGenericClient;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class FhirClientConfigurationTest {

    private final FhirClientConfiguration configuration = new FhirClientConfiguration();

    @Test
    void fhirContextIsR4() {
        FhirContext fhirContext = configuration.fhirContext();

        assertThat(fhirContext.getVersion().getVersion()).isEqualTo(FhirVersionEnum.R4);
    }

    @Test
    void fhirClientUsesConfiguredBaseUrl() {
        FhirContext fhirContext = configuration.fhirContext();
        FhirServerProperties properties = new FhirServerProperties("http://localhost:8080/fhir");

        IGenericClient client = configuration.fhirClient(fhirContext, properties);

        assertThat(client.getServerBase()).isEqualTo("http://localhost:8080/fhir");
    }

    @Test
    void fhirClientRejectsBlankBaseUrl() {
        FhirContext fhirContext = configuration.fhirContext();

        assertThatThrownBy(() -> configuration.fhirClient(fhirContext, new FhirServerProperties(" ")))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("fhir.server.base-url");
    }
}

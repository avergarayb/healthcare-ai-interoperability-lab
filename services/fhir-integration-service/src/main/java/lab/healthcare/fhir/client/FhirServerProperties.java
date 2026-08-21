package lab.healthcare.fhir.client;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "fhir.server")
public record FhirServerProperties(String baseUrl) {
}

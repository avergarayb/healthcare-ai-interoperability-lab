package lab.healthcare.fhir.client;

import org.springframework.boot.context.properties.ConfigurationProperties;

import java.util.Map;

@ConfigurationProperties(prefix = "fhir")
public record FhirServersProperties(String activeServer, Map<String, ServerSettings> servers) {

    public FhirServersProperties {
        servers = servers == null ? Map.of() : Map.copyOf(servers);
    }

    public record ServerSettings(
            String baseUrl,
            String fhirVersion,
            Boolean enabled,
            AuthenticationSettings authentication) {
    }

    public record AuthenticationSettings(
            String type,
            String tokenUrl,
            String clientId,
            String clientSecret,
            String smartConfigurationUrl,
            String redirectUri,
            String scope,
            String aud) {
    }
}

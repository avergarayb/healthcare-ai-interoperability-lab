package lab.healthcare.fhir.server;

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
            AuthenticationSettings authentication,
            String vendor,
            VendorIntegrationSettings vendorIntegration) {

        public static ServerSettings of(
                String baseUrl,
                String fhirVersion,
                Boolean enabled,
                AuthenticationSettings authentication) {
            return new ServerSettings(baseUrl, fhirVersion, enabled, authentication, null, null);
        }
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

    public record VendorIntegrationSettings(
            String environment,
            String launchMode,
            String userContext,
            String clientAuthentication,
            String patientId) {

        /**
         * Test helper. Not a binding constructor — Spring must use the
         * five-component canonical constructor so {@code patient-id} is applied.
         */
        public static VendorIntegrationSettings of(
                String environment, String launchMode, String userContext, String clientAuthentication) {
            return new VendorIntegrationSettings(environment, launchMode, userContext, clientAuthentication, "");
        }
    }
}

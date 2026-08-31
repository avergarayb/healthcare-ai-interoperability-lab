package lab.healthcare.fhir.vendor.epic;

import lab.healthcare.fhir.server.FhirServerProfile;
import lab.healthcare.fhir.server.FhirServerProfileRegistry;
import lab.healthcare.fhir.server.FhirServersProperties;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class EpicVendorConfiguration {

    @Bean
    public EpicProfileValidator epicProfileValidator() {
        return new EpicProfileValidator();
    }

    @Bean
    public EpicIntegrationProfile epicSandboxProfile(
            FhirServerProfileRegistry registry,
            FhirServersProperties properties) {
        FhirServerProfile server = registry.profile(EpicIntegrationProfile.SANDBOX_SERVER);
        FhirServersProperties.ServerSettings settings = properties.servers().get(EpicIntegrationProfile.SANDBOX_SERVER);
        FhirServersProperties.VendorIntegrationSettings extras =
                settings == null ? null : settings.vendorIntegration();
        return EpicIntegrationProfile.from(server, extras);
    }
}

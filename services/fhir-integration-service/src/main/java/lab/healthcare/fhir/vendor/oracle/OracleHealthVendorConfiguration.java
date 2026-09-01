package lab.healthcare.fhir.vendor.oracle;

import lab.healthcare.fhir.server.FhirServerProfile;
import lab.healthcare.fhir.server.FhirServerProfileRegistry;
import lab.healthcare.fhir.server.FhirServersProperties;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class OracleHealthVendorConfiguration {

    @Bean
    public OracleHealthProfileValidator oracleHealthProfileValidator() {
        return new OracleHealthProfileValidator();
    }

    @Bean
    public OracleSandboxProfileValidator oracleSandboxProfileValidator() {
        return new OracleSandboxProfileValidator();
    }

    @Bean
    public OracleSandboxConfiguration oracleSandboxConfiguration(OracleHealthIntegrationProfile profile) {
        return OracleSandboxConfiguration.from(profile);
    }

    @Bean
    public OracleHealthIntegrationProfile oracleHealthSandboxProfile(
            FhirServerProfileRegistry registry,
            FhirServersProperties properties) {
        FhirServerProfile server = registry.profile(OracleHealthIntegrationProfile.SANDBOX_SERVER);
        FhirServersProperties.ServerSettings settings =
                properties.servers().get(OracleHealthIntegrationProfile.SANDBOX_SERVER);
        FhirServersProperties.VendorIntegrationSettings extras =
                settings == null ? null : settings.vendorIntegration();
        return OracleHealthIntegrationProfile.from(server, extras);
    }
}

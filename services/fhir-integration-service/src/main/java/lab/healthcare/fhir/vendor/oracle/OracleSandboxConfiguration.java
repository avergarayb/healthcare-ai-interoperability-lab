package lab.healthcare.fhir.vendor.oracle;

import lab.healthcare.fhir.server.FhirDeploymentEnvironment;

/**
 * External Oracle Health sandbox settings bound from configuration. Does not
 * call Oracle Health or store secrets in {@code toString()}.
 */
public record OracleSandboxConfiguration(
        String destination,
        boolean enabled,
        FhirDeploymentEnvironment deploymentEnvironment,
        OracleHealthEnvironment vendorEnvironment,
        String fhirBaseUrl,
        String smartConfigurationUrl,
        String clientId,
        String redirectUri,
        String requestedScopes,
        String aud,
        OracleHealthClientAuthentication clientAuthentication) {

    public OracleSandboxConfiguration {
        if (destination == null || destination.isBlank()) {
            throw new IllegalArgumentException("Oracle sandbox destination must be provided");
        }
        destination = destination.trim();
        if (deploymentEnvironment == null) {
            deploymentEnvironment = FhirDeploymentEnvironment.SANDBOX;
        }
        if (vendorEnvironment == null) {
            vendorEnvironment = OracleHealthEnvironment.SANDBOX;
        }
        if (clientAuthentication == null) {
            clientAuthentication = OracleHealthClientAuthentication.PUBLIC_PKCE;
        }
        fhirBaseUrl = trimToEmpty(fhirBaseUrl);
        smartConfigurationUrl = trimToEmpty(smartConfigurationUrl);
        clientId = trimToEmpty(clientId);
        redirectUri = trimToEmpty(redirectUri);
        requestedScopes = trimToEmpty(requestedScopes);
        aud = trimToEmpty(aud);
    }

    public static OracleSandboxConfiguration from(OracleHealthIntegrationProfile profile) {
        if (profile == null) {
            throw new IllegalArgumentException("Oracle Health integration profile must be provided");
        }
        FhirDeploymentEnvironment deployment = profile.environment() == OracleHealthEnvironment.PRODUCTION
                ? FhirDeploymentEnvironment.PRODUCTION
                : FhirDeploymentEnvironment.SANDBOX;
        return new OracleSandboxConfiguration(
                profile.serverProfileName(),
                profile.enabled(),
                deployment,
                profile.environment(),
                profile.fhirBaseUrl(),
                profile.smartConfigurationUrl(),
                profile.clientId(),
                profile.redirectUri(),
                profile.requestedScopes(),
                profile.aud(),
                profile.clientAuthentication());
    }

    @Override
    public String toString() {
        return "OracleSandboxConfiguration[destination="
                + destination
                + ", enabled="
                + enabled
                + ", deploymentEnvironment="
                + deploymentEnvironment
                + ", vendorEnvironment="
                + vendorEnvironment
                + ", clientAuthentication="
                + clientAuthentication
                + ", hasBaseUrl="
                + !fhirBaseUrl.isBlank()
                + ", hasSmartConfigurationUrl="
                + !smartConfigurationUrl.isBlank()
                + ", hasClientId="
                + !clientId.isBlank()
                + ", hasRedirectUri="
                + !redirectUri.isBlank()
                + ", hasScopes="
                + !requestedScopes.isBlank()
                + ", hasAud="
                + !aud.isBlank()
                + "]";
    }

    private static String trimToEmpty(String value) {
        return value == null ? "" : value.trim();
    }
}

package lab.healthcare.fhir.vendor.oracle;

import lab.healthcare.fhir.auth.FhirAuthenticationSettings;
import lab.healthcare.fhir.auth.FhirAuthenticationType;
import lab.healthcare.fhir.server.FhirServerProfile;
import lab.healthcare.fhir.server.FhirServersProperties;
import lab.healthcare.fhir.vendor.FhirVendor;
import lab.healthcare.fhir.vendor.FhirVendorProfile;

/**
 * Vendor-known Oracle Health integration metadata for one named server profile.
 * Does not perform OAuth or call Oracle Health. FHIR base URL and discovery come
 * from configuration; Java does not concatenate vendor hostnames.
 */
public record OracleHealthIntegrationProfile(
        FhirVendorProfile vendorProfile,
        String fhirVersion,
        String fhirBaseUrl,
        String smartConfigurationUrl,
        String clientId,
        String redirectUri,
        String requestedScopes,
        String aud,
        boolean enabled,
        OracleHealthEnvironment environment,
        OracleHealthLaunchMode launchMode,
        OracleHealthUserContext userContext,
        OracleHealthClientAuthentication clientAuthentication,
        OracleHealthCapabilities capabilities,
        OracleHealthReadinessState readiness) {

    public static final String SANDBOX_SERVER = "oracle-health-sandbox";

    public OracleHealthIntegrationProfile {
        if (vendorProfile == null) {
            throw new IllegalArgumentException("vendor profile must be provided");
        }
        fhirVersion = trimToEmpty(fhirVersion);
        fhirBaseUrl = trimToEmpty(fhirBaseUrl);
        smartConfigurationUrl = trimToEmpty(smartConfigurationUrl);
        clientId = trimToEmpty(clientId);
        redirectUri = trimToEmpty(redirectUri);
        requestedScopes = trimToEmpty(requestedScopes);
        aud = trimToEmpty(aud);
        if (environment == null) {
            environment = OracleHealthEnvironment.SANDBOX;
        }
        if (launchMode == null) {
            launchMode = OracleHealthLaunchMode.STANDALONE;
        }
        if (userContext == null) {
            userContext = OracleHealthUserContext.PATIENT;
        }
        if (clientAuthentication == null) {
            clientAuthentication = OracleHealthClientAuthentication.PUBLIC_PKCE;
        }
        if (capabilities == null) {
            capabilities = OracleHealthCapabilities.forProfile(fhirVersion, launchMode, clientAuthentication);
        }
        if (readiness == null) {
            readiness = OracleHealthReadinessState.NOT_CONFIGURED;
        }
    }

    public static OracleHealthIntegrationProfile from(
            FhirServerProfile server,
            FhirServersProperties.VendorIntegrationSettings extras) {
        if (server == null) {
            throw new IllegalArgumentException("FHIR server profile must be provided");
        }
        FhirAuthenticationSettings authentication = server.authentication();
        OracleHealthEnvironment environment = extras == null
                ? OracleHealthEnvironment.SANDBOX
                : OracleHealthEnvironment.fromConfiguration(extras.environment());
        OracleHealthLaunchMode launchMode = extras == null
                ? OracleHealthLaunchMode.STANDALONE
                : OracleHealthLaunchMode.fromConfiguration(extras.launchMode());
        OracleHealthUserContext userContext = extras == null
                ? OracleHealthUserContext.PATIENT
                : OracleHealthUserContext.fromConfiguration(extras.userContext());
        OracleHealthClientAuthentication clientAuthentication = extras == null
                ? OracleHealthClientAuthentication.PUBLIC_PKCE
                : OracleHealthClientAuthentication.fromConfiguration(extras.clientAuthentication());
        OracleHealthCapabilities capabilities = OracleHealthCapabilities.forProfile(
                server.fhirVersion(), launchMode, clientAuthentication);
        return new OracleHealthIntegrationProfile(
                new FhirVendorProfile(server.vendor(), server.name()),
                server.fhirVersion(),
                server.baseUrl(),
                authentication == null ? "" : nullToEmpty(authentication.smartConfigurationUrl()),
                authentication == null ? "" : nullToEmpty(authentication.clientId()),
                authentication == null ? "" : nullToEmpty(authentication.redirectUri()),
                authentication == null ? "" : nullToEmpty(authentication.scope()),
                authentication == null ? "" : nullToEmpty(authentication.aud()),
                server.enabled(),
                environment,
                launchMode,
                userContext,
                clientAuthentication,
                capabilities,
                readinessOf(
                        server,
                        authentication,
                        environment,
                        clientAuthentication,
                        capabilities));
    }

    public FhirVendor vendor() {
        return vendorProfile.vendor();
    }

    public String serverProfileName() {
        return vendorProfile.serverProfileName();
    }

    public boolean hasRequestedScopes() {
        return !requestedScopes.isBlank();
    }

    public FhirAuthenticationSettings toAuthenticationSettings() {
        return new FhirAuthenticationSettings(
                FhirAuthenticationType.SMART_AUTHORIZATION_CODE,
                null,
                clientId,
                "",
                smartConfigurationUrl.isBlank() ? null : smartConfigurationUrl,
                redirectUri,
                requestedScopes,
                aud);
    }

    /**
     * Public {@code GET /metadata} must not attach a SMART Bearer token. The named
     * sandbox profile stays {@code SMART_AUTHORIZATION_CODE}; this copy uses the
     * same configured base URL with {@code NONE} so discovery does not invent a
     * synthetic authorization.
     */
    public FhirServerProfile toUnauthenticatedMetadataProfile() {
        return new FhirServerProfile(
                serverProfileName(),
                fhirBaseUrl,
                fhirVersion,
                true,
                vendor(),
                FhirAuthenticationSettings.none());
    }

    @Override
    public String toString() {
        return "OracleHealthIntegrationProfile[server="
                + serverProfileName()
                + ", vendor="
                + vendor()
                + ", environment="
                + environment
                + ", fhirVersion="
                + fhirVersion
                + ", launchMode="
                + launchMode
                + ", userContext="
                + userContext
                + ", clientAuthentication="
                + clientAuthentication
                + ", enabled="
                + enabled
                + ", readiness="
                + readiness
                + ", hasClientId="
                + !clientId.isBlank()
                + ", hasRedirectUri="
                + !redirectUri.isBlank()
                + ", hasScopes="
                + hasRequestedScopes()
                + ", hasAud="
                + !aud.isBlank()
                + ", hasBaseUrl="
                + !fhirBaseUrl.isBlank()
                + "]";
    }

    private static OracleHealthReadinessState readinessOf(
            FhirServerProfile server,
            FhirAuthenticationSettings authentication,
            OracleHealthEnvironment environment,
            OracleHealthClientAuthentication clientAuthentication,
            OracleHealthCapabilities capabilities) {
        boolean configured = present(server.baseUrl())
                && present(server.fhirVersion())
                && authentication != null
                && present(authentication.aud())
                && present(authentication.clientId())
                && present(authentication.redirectUri())
                && present(authentication.scope())
                && present(authentication.smartConfigurationUrl());
        if (!configured) {
            return OracleHealthReadinessState.NOT_CONFIGURED;
        }
        boolean smartCompatible = authentication.isSmartAuthorizationCode()
                && clientAuthentication.runtimeSupported()
                && capabilities.supportsR4();
        if (!smartCompatible) {
            return OracleHealthReadinessState.CONFIGURED;
        }
        if (environment == OracleHealthEnvironment.SANDBOX && server.vendor() == FhirVendor.ORACLE_HEALTH) {
            return OracleHealthReadinessState.READY_FOR_SANDBOX;
        }
        return OracleHealthReadinessState.SMART_COMPATIBLE;
    }

    private static boolean present(String value) {
        return value != null && !value.isBlank();
    }

    private static String nullToEmpty(String value) {
        return value == null ? "" : value;
    }

    private static String trimToEmpty(String value) {
        return value == null ? "" : value.trim();
    }
}

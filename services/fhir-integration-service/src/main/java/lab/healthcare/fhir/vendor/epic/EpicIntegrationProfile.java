package lab.healthcare.fhir.vendor.epic;

import lab.healthcare.fhir.auth.FhirAuthenticationSettings;
import lab.healthcare.fhir.auth.FhirAuthenticationType;
import lab.healthcare.fhir.server.FhirServerProfile;
import lab.healthcare.fhir.server.FhirServersProperties;
import lab.healthcare.fhir.vendor.FhirVendor;
import lab.healthcare.fhir.vendor.FhirVendorProfile;

/**
 * Vendor-known Epic integration metadata for one named server profile.
 * Does not perform OAuth or call Epic.
 */
public record EpicIntegrationProfile(
        FhirVendorProfile vendorProfile,
        String fhirVersion,
        String fhirBaseUrl,
        String smartConfigurationUrl,
        String clientId,
        String redirectUri,
        String requestedScopes,
        String aud,
        boolean enabled,
        EpicEnvironment environment,
        EpicLaunchMode launchMode,
        EpicUserContext userContext,
        EpicClientAuthentication clientAuthentication,
        EpicCapabilities capabilities,
        EpicReadinessState readiness,
        String configuredPatientId) {

    public static final String SANDBOX_SERVER = "epic-sandbox";

    public EpicIntegrationProfile {
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
            environment = EpicEnvironment.SANDBOX;
        }
        if (launchMode == null) {
            launchMode = EpicLaunchMode.STANDALONE;
        }
        if (userContext == null) {
            userContext = EpicUserContext.PATIENT;
        }
        if (clientAuthentication == null) {
            clientAuthentication = EpicClientAuthentication.PUBLIC_PKCE;
        }
        if (capabilities == null) {
            capabilities = EpicCapabilities.forProfile(fhirVersion, launchMode, clientAuthentication);
        }
        if (readiness == null) {
            readiness = EpicReadinessState.NOT_CONFIGURED;
        }
        configuredPatientId = trimToEmpty(configuredPatientId);
    }

    public static EpicIntegrationProfile from(
            FhirServerProfile server,
            FhirServersProperties.VendorIntegrationSettings extras) {
        if (server == null) {
            throw new IllegalArgumentException("FHIR server profile must be provided");
        }
        FhirAuthenticationSettings authentication = server.authentication();
        EpicEnvironment environment = extras == null
                ? EpicEnvironment.SANDBOX
                : EpicEnvironment.fromConfiguration(extras.environment());
        EpicLaunchMode launchMode = extras == null
                ? EpicLaunchMode.STANDALONE
                : EpicLaunchMode.fromConfiguration(extras.launchMode());
        EpicUserContext userContext = extras == null
                ? EpicUserContext.PATIENT
                : EpicUserContext.fromConfiguration(extras.userContext());
        EpicClientAuthentication clientAuthentication = extras == null
                ? EpicClientAuthentication.PUBLIC_PKCE
                : EpicClientAuthentication.fromConfiguration(extras.clientAuthentication());
        EpicCapabilities capabilities = EpicCapabilities.forProfile(
                server.fhirVersion(), launchMode, clientAuthentication);
        return new EpicIntegrationProfile(
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
                        capabilities),
                extras == null ? "" : nullToEmpty(extras.patientId()));
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

    public boolean hasConfiguredPatientId() {
        return !configuredPatientId.isBlank();
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
        return "EpicIntegrationProfile[server="
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
                + ", hasConfiguredPatientId="
                + hasConfiguredPatientId()
                + "]";
    }

    private static EpicReadinessState readinessOf(
            FhirServerProfile server,
            FhirAuthenticationSettings authentication,
            EpicEnvironment environment,
            EpicClientAuthentication clientAuthentication,
            EpicCapabilities capabilities) {
        boolean configured = present(server.baseUrl())
                && present(server.fhirVersion())
                && authentication != null
                && present(authentication.aud())
                && present(authentication.clientId())
                && present(authentication.redirectUri())
                && present(authentication.scope())
                && present(authentication.smartConfigurationUrl());
        if (!configured) {
            return EpicReadinessState.NOT_CONFIGURED;
        }
        boolean smartCompatible = authentication.isSmartAuthorizationCode()
                && clientAuthentication.runtimeSupported()
                && capabilities.supportsR4();
        if (!smartCompatible) {
            return EpicReadinessState.CONFIGURED;
        }
        if (environment == EpicEnvironment.SANDBOX && server.vendor() == FhirVendor.EPIC) {
            return EpicReadinessState.READY_FOR_SANDBOX;
        }
        return EpicReadinessState.SMART_COMPATIBLE;
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

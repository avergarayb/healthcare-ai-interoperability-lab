package lab.healthcare.fhir.smart;

import lab.healthcare.fhir.auth.FhirAuthenticationSettings;

/**
 * Explicit source of {@code /.well-known/smart-configuration}.
 * The URL is configured on the FHIR server profile. Vendor hosts are not concatenated here.
 */
public final class SmartDiscoveryUrl {

    private SmartDiscoveryUrl() {
    }

    public static String from(FhirAuthenticationSettings authentication) {
        if (authentication == null || !authentication.isSmartAuthorizationCode()) {
            throw new IllegalArgumentException("SMART authorization code settings must be provided");
        }
        String url = authentication.smartConfigurationUrl();
        if (url == null || url.isBlank()) {
            throw new IllegalArgumentException("SMART discovery URL must be configured on the server profile");
        }
        return url.trim();
    }
}

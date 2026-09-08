package lab.healthcare.fhir.vendor.epic;

import lab.healthcare.fhir.vendor.FhirVendor;

import java.net.URI;

/**
 * Answers whether an Epic profile is sufficiently configured for the intended mode.
 * Does not call Epic, discover SMART, or execute FHIR.
 */
public class EpicProfileValidator {

    public void validate(EpicIntegrationProfile profile) {
        validate(profile, false);
    }

    public void validateForRuntime(EpicIntegrationProfile profile) {
        validate(profile, true);
    }

    public void validateForAuthorization(EpicIntegrationProfile profile) {
        if (profile == null) {
            throw new EpicProfileException("Epic integration profile is missing");
        }
        if (!profile.enabled()) {
            throw new EpicProfileException("Epic sandbox profile is disabled");
        }
        if (profile.environment() != EpicEnvironment.SANDBOX) {
            throw new EpicProfileException("Epic authorization is only supported for SANDBOX");
        }
        validate(profile, true);
        requireHttpUri(profile.fhirBaseUrl(), "FHIR base URL");
        requireHttpUri(profile.aud(), "aud");
        requireHttpUri(profile.redirectUri(), "redirect URI");
        requireHttpUri(profile.smartConfigurationUrl(), "SMART configuration URL");
    }

    private void validate(EpicIntegrationProfile profile, boolean requireRuntime) {
        if (profile == null) {
            throw new EpicProfileException("Epic integration profile is missing");
        }
        if (profile.vendor() != FhirVendor.EPIC) {
            throw new EpicProfileException("Epic integration profile vendor must be EPIC");
        }
        if (profile.fhirVersion() == null || !"R4".equalsIgnoreCase(profile.fhirVersion())) {
            throw new EpicProfileException("Epic integration profile FHIR version must be R4");
        }
        if (isBlank(profile.fhirBaseUrl())) {
            throw new EpicProfileException("Epic integration profile is missing FHIR base URL");
        }
        if (isBlank(profile.aud())) {
            throw new EpicProfileException("Epic integration profile is missing aud");
        }
        if (profile.enabled() || requireRuntime) {
            if (isBlank(profile.clientId())) {
                throw new EpicProfileException("Enabled Epic profile is missing client ID");
            }
            if (isBlank(profile.redirectUri())) {
                throw new EpicProfileException("Enabled Epic Authorization Code profile is missing redirect URI");
            }
            if (isBlank(profile.requestedScopes())) {
                throw new EpicProfileException("Enabled Epic profile is missing requested scopes");
            }
            if (isBlank(profile.smartConfigurationUrl())) {
                throw new EpicProfileException("Enabled Epic profile is missing SMART configuration URL");
            }
        }
        if (requireRuntime && !profile.clientAuthentication().runtimeSupported()) {
            throw new EpicProfileException(
                    "Epic client authentication "
                            + profile.clientAuthentication()
                            + " is not supported by the current runtime");
        }
    }

    private static void requireHttpUri(String value, String field) {
        if (isBlank(value)) {
            throw new EpicProfileException("Epic sandbox " + field + " must be provided");
        }
        URI uri;
        try {
            uri = URI.create(value.trim());
        } catch (IllegalArgumentException ex) {
            throw new EpicProfileException("Epic sandbox " + field + " is not a valid URI");
        }
        String scheme = uri.getScheme();
        if (scheme == null || !(scheme.equalsIgnoreCase("http") || scheme.equalsIgnoreCase("https"))) {
            throw new EpicProfileException("Epic sandbox " + field + " must be an http(s) URI");
        }
        if (uri.getHost() == null || uri.getHost().isBlank()) {
            throw new EpicProfileException("Epic sandbox " + field + " is missing a host");
        }
        if (uri.getUserInfo() != null) {
            throw new EpicProfileException("Epic sandbox " + field + " must not contain credentials");
        }
    }

    private static boolean isBlank(String value) {
        return value == null || value.isBlank();
    }
}

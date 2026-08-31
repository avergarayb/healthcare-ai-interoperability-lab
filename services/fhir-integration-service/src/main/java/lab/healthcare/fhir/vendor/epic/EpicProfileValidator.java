package lab.healthcare.fhir.vendor.epic;

import lab.healthcare.fhir.vendor.FhirVendor;

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

    private static boolean isBlank(String value) {
        return value == null || value.isBlank();
    }
}

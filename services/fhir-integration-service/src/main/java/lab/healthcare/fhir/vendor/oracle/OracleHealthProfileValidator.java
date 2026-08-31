package lab.healthcare.fhir.vendor.oracle;

import lab.healthcare.fhir.vendor.FhirVendor;

/**
 * Answers whether an Oracle Health profile is sufficiently configured for the intended mode.
 * Does not call Oracle Health, discover SMART, or execute FHIR.
 */
public class OracleHealthProfileValidator {

    public void validate(OracleHealthIntegrationProfile profile) {
        validate(profile, false);
    }

    public void validateForRuntime(OracleHealthIntegrationProfile profile) {
        validate(profile, true);
    }

    private void validate(OracleHealthIntegrationProfile profile, boolean requireRuntime) {
        if (profile == null) {
            throw new OracleHealthProfileException("Oracle Health integration profile is missing");
        }
        if (profile.vendor() != FhirVendor.ORACLE_HEALTH) {
            throw new OracleHealthProfileException("Oracle Health integration profile vendor must be ORACLE_HEALTH");
        }
        boolean versionPresent = profile.fhirVersion() != null && !profile.fhirVersion().isBlank();
        if (versionPresent && !"R4".equalsIgnoreCase(profile.fhirVersion())) {
            throw new OracleHealthProfileException("Oracle Health integration profile FHIR version must be R4");
        }
        if (profile.enabled() || requireRuntime) {
            if (!versionPresent || !"R4".equalsIgnoreCase(profile.fhirVersion())) {
                throw new OracleHealthProfileException("Oracle Health integration profile FHIR version must be R4");
            }
            if (isBlank(profile.fhirBaseUrl())) {
                throw new OracleHealthProfileException("Oracle Health integration profile is missing FHIR base URL");
            }
            if (isBlank(profile.aud())) {
                throw new OracleHealthProfileException("Oracle Health integration profile is missing aud");
            }
            if (isBlank(profile.clientId())) {
                throw new OracleHealthProfileException("Enabled Oracle Health profile is missing client ID");
            }
            if (isBlank(profile.redirectUri())) {
                throw new OracleHealthProfileException(
                        "Enabled Oracle Health Authorization Code profile is missing redirect URI");
            }
            if (isBlank(profile.requestedScopes())) {
                throw new OracleHealthProfileException("Enabled Oracle Health profile is missing requested scopes");
            }
            if (isBlank(profile.smartConfigurationUrl())) {
                throw new OracleHealthProfileException(
                        "Enabled Oracle Health profile is missing SMART configuration URL");
            }
        }
        if (requireRuntime && !profile.clientAuthentication().runtimeSupported()) {
            throw new OracleHealthProfileException(
                    "Oracle Health client authentication "
                            + profile.clientAuthentication()
                            + " is not supported by the current runtime");
        }
    }

    private static boolean isBlank(String value) {
        return value == null || value.isBlank();
    }
}

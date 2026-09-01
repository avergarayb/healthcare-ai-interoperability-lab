package lab.healthcare.fhir.vendor.oracle;

import java.net.URI;

/**
 * Fail-fast validation for an Oracle Health sandbox that may be enabled for
 * external connectivity. Does not call Oracle Health.
 */
public class OracleSandboxProfileValidator {

    private final OracleHealthProfileValidator profileValidator = new OracleHealthProfileValidator();

    public void validateDisabledAllowed(OracleHealthIntegrationProfile profile) {
        profileValidator.validate(profile);
    }

    public void validateForConnectivity(OracleHealthIntegrationProfile profile) {
        if (profile == null) {
            throw new OracleHealthProfileException("Oracle Health integration profile is missing");
        }
        if (!profile.enabled()) {
            return;
        }
        profileValidator.validate(profile);
        profileValidator.validateForRuntime(profile);
        if (profile.environment() != OracleHealthEnvironment.SANDBOX) {
            throw new OracleHealthProfileException(
                    "Oracle Health connectivity check is only supported for SANDBOX");
        }
        requireHttpUri(profile.fhirBaseUrl(), "FHIR base URL");
        requireHttpUri(profile.aud(), "aud");
        requireHttpUri(profile.redirectUri(), "redirect URI");
        requireHttpUri(profile.smartConfigurationUrl(), "SMART configuration URL");
    }

    private static void requireHttpUri(String value, String field) {
        if (value == null || value.isBlank()) {
            throw new OracleHealthProfileException("Oracle Health sandbox " + field + " must be provided");
        }
        URI uri;
        try {
            uri = URI.create(value.trim());
        } catch (IllegalArgumentException ex) {
            throw new OracleHealthProfileException("Oracle Health sandbox " + field + " is not a valid URI");
        }
        String scheme = uri.getScheme();
        if (scheme == null || !(scheme.equalsIgnoreCase("http") || scheme.equalsIgnoreCase("https"))) {
            throw new OracleHealthProfileException("Oracle Health sandbox " + field + " must be an http(s) URI");
        }
        if (uri.getHost() == null || uri.getHost().isBlank()) {
            throw new OracleHealthProfileException("Oracle Health sandbox " + field + " is missing a host");
        }
        if (uri.getUserInfo() != null) {
            throw new OracleHealthProfileException("Oracle Health sandbox " + field + " must not contain credentials");
        }
    }
}

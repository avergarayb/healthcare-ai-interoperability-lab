package lab.healthcare.fhir.smart;

/**
 * Answers whether discovered SMART metadata can run this platform's current flow.
 * Does not execute OAuth, open a browser, or call {@code FhirService}.
 */
public class SmartConfigurationValidator {

    public void validate(SmartConfiguration configuration) {
        validate(configuration, SmartFlowRequirements.authorizationCodePkceS256());
    }

    public void validate(SmartConfiguration configuration, SmartFlowRequirements requirements) {
        if (configuration == null) {
            throw new SmartCompatibilityException("SMART configuration is missing");
        }
        if (requirements == null) {
            throw new IllegalArgumentException("SMART flow requirements must be provided");
        }
        if (requirements.requireAuthorizationEndpoint() && isBlank(configuration.authorizationEndpoint())) {
            throw new SmartCompatibilityException("SMART metadata is missing authorization_endpoint");
        }
        if (requirements.requireTokenEndpoint() && isBlank(configuration.tokenEndpoint())) {
            throw new SmartCompatibilityException("SMART metadata is missing token_endpoint");
        }
        SmartCapabilities capabilities = SmartCapabilities.from(configuration);
        if (requirements.requireAuthorizationCodeWhenDeclared()
                && capabilities.declaresGrantTypes()
                && !capabilities.declaresAuthorizationCode()) {
            throw new SmartCompatibilityException(
                    "SMART metadata grant_types_supported does not include authorization_code");
        }
        if (requirements.requirePkceS256WhenDeclared()
                && capabilities.declaresChallengeMethods()
                && !capabilities.declaresPkceS256()) {
            throw new SmartCompatibilityException(
                    "SMART metadata code_challenge_methods_supported does not include S256");
        }
    }

    private static boolean isBlank(String value) {
        return value == null || value.isBlank();
    }
}

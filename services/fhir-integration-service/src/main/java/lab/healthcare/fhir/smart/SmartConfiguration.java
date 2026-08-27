package lab.healthcare.fhir.smart;

import java.util.List;

public record SmartConfiguration(
        String authorizationEndpoint,
        String tokenEndpoint,
        List<String> scopesSupported,
        List<String> responseTypesSupported,
        List<String> codeChallengeMethodsSupported,
        List<String> capabilities) {
}

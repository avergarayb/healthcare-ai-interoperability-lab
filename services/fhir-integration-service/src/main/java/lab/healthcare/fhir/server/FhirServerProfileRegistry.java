package lab.healthcare.fhir.server;

import lab.healthcare.fhir.auth.FhirAuthenticationSettings;
import lab.healthcare.fhir.auth.FhirAuthenticationType;

import java.util.LinkedHashMap;
import java.util.Locale;
import java.util.Map;

public class FhirServerProfileRegistry {

    private final FhirServersProperties properties;

    public FhirServerProfileRegistry(FhirServersProperties properties) {
        if (properties == null) {
            throw new IllegalArgumentException("FHIR server properties must be provided");
        }
        this.properties = properties;
    }

    public FhirServerProfile activeProfile() {
        String name = properties.activeServer();
        if (name == null || name.isBlank()) {
            throw new IllegalStateException("Property fhir.active-server must be set");
        }
        return enabledProfile(name.trim());
    }

    public FhirServerProfile enabledProfile(String name) {
        FhirServerProfile profile = profile(name);
        if (!profile.enabled()) {
            throw new IllegalStateException("FHIR server profile '" + profile.name() + "' is disabled");
        }
        requireSecretWhenClientCredentialsEnabled(profile);
        return profile;
    }

    public FhirServerProfile profile(String name) {
        if (name == null || name.isBlank()) {
            throw new IllegalArgumentException("FHIR server profile name must be provided");
        }
        Map<String, FhirServersProperties.ServerSettings> servers = properties.servers();
        if (servers.isEmpty()) {
            throw new IllegalStateException("Property fhir.servers must define at least one profile");
        }
        FhirServersProperties.ServerSettings settings = servers.get(name);
        if (settings == null) {
            throw new IllegalStateException("Unknown FHIR server profile '" + name + "'");
        }
        String baseUrl = settings.baseUrl();
        if (baseUrl == null || baseUrl.isBlank()) {
            throw new IllegalStateException("Property fhir.servers." + name + ".base-url must be set");
        }
        String fhirVersion = settings.fhirVersion();
        if (fhirVersion == null || fhirVersion.isBlank()) {
            throw new IllegalStateException("Property fhir.servers." + name + ".fhir-version must be set");
        }
        boolean enabled = Boolean.TRUE.equals(settings.enabled());
        FhirAuthenticationSettings authentication = authentication(name, settings.authentication());
        return new FhirServerProfile(name, baseUrl.trim(), fhirVersion.trim(), enabled, authentication);
    }

    public Map<String, FhirServerProfile> profiles() {
        Map<String, FhirServerProfile> profiles = new LinkedHashMap<>();
        for (String name : properties.servers().keySet()) {
            profiles.put(name, profile(name));
        }
        return Map.copyOf(profiles);
    }

    private static FhirAuthenticationSettings authentication(
            String profileName,
            FhirServersProperties.AuthenticationSettings raw) {
        if (raw == null || raw.type() == null || raw.type().isBlank()) {
            return FhirAuthenticationSettings.none();
        }
        FhirAuthenticationType type;
        try {
            type = FhirAuthenticationType.valueOf(raw.type().trim().toUpperCase(Locale.ROOT));
        } catch (IllegalArgumentException ex) {
            throw new IllegalStateException(
                    "Property fhir.servers." + profileName + ".authentication.type is unsupported: " + raw.type(),
                    ex);
        }
        if (type == FhirAuthenticationType.NONE) {
            return FhirAuthenticationSettings.none();
        }
        String clientId = required(raw.clientId(), profileName, "client-id");
        if (type == FhirAuthenticationType.OAUTH2_CLIENT_CREDENTIALS) {
            String tokenUrl = required(raw.tokenUrl(), profileName, "token-url");
            String clientSecret = raw.clientSecret() == null ? "" : raw.clientSecret();
            return new FhirAuthenticationSettings(type, tokenUrl, clientId, clientSecret);
        }
        String smartConfigurationUrl = required(raw.smartConfigurationUrl(), profileName, "smart-configuration-url");
        String redirectUri = required(raw.redirectUri(), profileName, "redirect-uri");
        String scope = required(raw.scope(), profileName, "scope");
        String aud = required(raw.aud(), profileName, "aud");
        return new FhirAuthenticationSettings(
                type,
                null,
                clientId,
                "",
                smartConfigurationUrl.trim(),
                redirectUri.trim(),
                scope.trim(),
                aud.trim());
    }

    private static String required(String value, String profileName, String property) {
        if (value == null || value.isBlank()) {
            throw new IllegalStateException(
                    "Property fhir.servers." + profileName + ".authentication." + property + " must be set");
        }
        return value.trim();
    }

    private static void requireSecretWhenClientCredentialsEnabled(FhirServerProfile profile) {
        FhirAuthenticationSettings authentication = profile.authentication();
        if (!authentication.isClientCredentials()) {
            return;
        }
        String secret = authentication.clientSecret();
        if (secret == null || secret.isBlank()) {
            throw new IllegalStateException(
                    "Property fhir.servers." + profile.name() + ".authentication.client-secret must be set");
        }
    }
}

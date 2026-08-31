package lab.healthcare.fhir.server;

import lab.healthcare.fhir.auth.FhirAuthenticationSettings;
import lab.healthcare.fhir.auth.FhirAuthenticationType;
import lab.healthcare.fhir.vendor.FhirVendor;

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
        requireSmartFieldsWhenEnabled(profile);
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
        String fhirVersion = settings.fhirVersion();
        if (fhirVersion == null || fhirVersion.isBlank()) {
            throw new IllegalStateException("Property fhir.servers." + name + ".fhir-version must be set");
        }
        boolean enabled = Boolean.TRUE.equals(settings.enabled());
        if ((baseUrl == null || baseUrl.isBlank()) && enabled) {
            throw new IllegalStateException("Property fhir.servers." + name + ".base-url must be set");
        }
        FhirAuthenticationSettings authentication = authentication(name, enabled, settings.authentication());
        return new FhirServerProfile(
                name,
                baseUrl == null || baseUrl.isBlank() ? "" : baseUrl.trim(),
                fhirVersion.trim(),
                enabled,
                FhirVendor.fromConfiguration(settings.vendor()),
                authentication);
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
            boolean enabled,
            FhirServersProperties.AuthenticationSettings raw) {
        if (raw == null || raw.type() == null || raw.type().isBlank()) {
            return FhirAuthenticationSettings.none();
        }
        FhirAuthenticationType type;
        try {
            type = parseAuthenticationType(raw.type());
        } catch (IllegalArgumentException ex) {
            throw new IllegalStateException(
                    "Property fhir.servers." + profileName + ".authentication.type is unsupported: " + raw.type(),
                    ex);
        }
        if (type == FhirAuthenticationType.NONE) {
            return FhirAuthenticationSettings.none();
        }
        if (type == FhirAuthenticationType.OAUTH2_CLIENT_CREDENTIALS) {
            String tokenUrl = required(raw.tokenUrl(), profileName, "token-url");
            String clientId = required(raw.clientId(), profileName, "client-id");
            String clientSecret = raw.clientSecret() == null ? "" : raw.clientSecret();
            return new FhirAuthenticationSettings(type, tokenUrl, clientId, clientSecret);
        }
        if (!enabled) {
            return new FhirAuthenticationSettings(
                    type,
                    null,
                    optional(raw.clientId()),
                    "",
                    blankToNull(raw.smartConfigurationUrl()),
                    optional(raw.redirectUri()),
                    optional(raw.scope()),
                    optional(raw.aud()));
        }
        String clientId = required(raw.clientId(), profileName, "client-id");
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

    private static FhirAuthenticationType parseAuthenticationType(String raw) {
        String normalized = raw.trim().toUpperCase(Locale.ROOT);
        if ("SMART".equals(normalized)) {
            return FhirAuthenticationType.SMART_AUTHORIZATION_CODE;
        }
        return FhirAuthenticationType.valueOf(normalized);
    }

    private static String required(String value, String profileName, String property) {
        if (value == null || value.isBlank()) {
            throw new IllegalStateException(
                    "Property fhir.servers." + profileName + ".authentication." + property + " must be set");
        }
        return value.trim();
    }

    private static String optional(String value) {
        return value == null || value.isBlank() ? "" : value.trim();
    }

    private static String blankToNull(String value) {
        return value == null || value.isBlank() ? null : value.trim();
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

    private static void requireSmartFieldsWhenEnabled(FhirServerProfile profile) {
        FhirAuthenticationSettings authentication = profile.authentication();
        if (!authentication.isSmartAuthorizationCode()) {
            return;
        }
        if (authentication.clientId() == null || authentication.clientId().isBlank()) {
            throw new IllegalStateException(
                    "Property fhir.servers." + profile.name() + ".authentication.client-id must be set");
        }
        if (authentication.redirectUri() == null || authentication.redirectUri().isBlank()) {
            throw new IllegalStateException(
                    "Property fhir.servers." + profile.name() + ".authentication.redirect-uri must be set");
        }
        if (authentication.scope() == null || authentication.scope().isBlank()) {
            throw new IllegalStateException(
                    "Property fhir.servers." + profile.name() + ".authentication.scope must be set");
        }
        if (authentication.aud() == null || authentication.aud().isBlank()) {
            throw new IllegalStateException(
                    "Property fhir.servers." + profile.name() + ".authentication.aud must be set");
        }
        if (authentication.smartConfigurationUrl() == null || authentication.smartConfigurationUrl().isBlank()) {
            throw new IllegalStateException(
                    "Property fhir.servers."
                            + profile.name()
                            + ".authentication.smart-configuration-url must be set");
        }
    }
}

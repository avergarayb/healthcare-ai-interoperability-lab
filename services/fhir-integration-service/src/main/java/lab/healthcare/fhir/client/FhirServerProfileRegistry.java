package lab.healthcare.fhir.client;

import java.util.LinkedHashMap;
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
        FhirServerProfile profile = profile(name.trim());
        if (!profile.enabled()) {
            throw new IllegalStateException("FHIR server profile '" + profile.name() + "' is disabled");
        }
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
        return new FhirServerProfile(name, baseUrl.trim(), fhirVersion.trim(), enabled);
    }

    public Map<String, FhirServerProfile> profiles() {
        Map<String, FhirServerProfile> profiles = new LinkedHashMap<>();
        for (String name : properties.servers().keySet()) {
            profiles.put(name, profile(name));
        }
        return Map.copyOf(profiles);
    }
}

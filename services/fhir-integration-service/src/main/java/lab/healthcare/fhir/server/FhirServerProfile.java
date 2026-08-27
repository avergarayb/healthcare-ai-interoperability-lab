package lab.healthcare.fhir.server;

import lab.healthcare.fhir.auth.FhirAuthenticationSettings;

/**
 * Named connectivity settings for one FHIR server. Not a FHIR StructureDefinition profile.
 */
public record FhirServerProfile(
        String name,
        String baseUrl,
        String fhirVersion,
        boolean enabled,
        FhirAuthenticationSettings authentication) {

    public FhirServerProfile {
        authentication = authentication == null ? FhirAuthenticationSettings.none() : authentication;
    }

    public FhirServerProfile(String name, String baseUrl, String fhirVersion, boolean enabled) {
        this(name, baseUrl, fhirVersion, enabled, FhirAuthenticationSettings.none());
    }
}

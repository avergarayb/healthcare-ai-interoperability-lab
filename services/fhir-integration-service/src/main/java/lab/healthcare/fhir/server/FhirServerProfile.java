package lab.healthcare.fhir.server;

import lab.healthcare.fhir.auth.FhirAuthenticationSettings;
import lab.healthcare.fhir.vendor.FhirVendor;

/**
 * Named connectivity settings for one FHIR server. Not a FHIR StructureDefinition profile.
 */
public record FhirServerProfile(
        String name,
        String baseUrl,
        String fhirVersion,
        boolean enabled,
        FhirVendor vendor,
        FhirAuthenticationSettings authentication) {

    public FhirServerProfile {
        vendor = vendor == null ? FhirVendor.GENERIC : vendor;
        authentication = authentication == null ? FhirAuthenticationSettings.none() : authentication;
    }

    public FhirServerProfile(
            String name,
            String baseUrl,
            String fhirVersion,
            boolean enabled,
            FhirAuthenticationSettings authentication) {
        this(name, baseUrl, fhirVersion, enabled, FhirVendor.GENERIC, authentication);
    }

    public FhirServerProfile(String name, String baseUrl, String fhirVersion, boolean enabled) {
        this(name, baseUrl, fhirVersion, enabled, FhirVendor.GENERIC, FhirAuthenticationSettings.none());
    }
}

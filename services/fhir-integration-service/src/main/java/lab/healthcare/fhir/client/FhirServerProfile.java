package lab.healthcare.fhir.client;

/**
 * Named connectivity settings for one FHIR server. Not a FHIR StructureDefinition profile.
 */
public record FhirServerProfile(String name, String baseUrl, String fhirVersion, boolean enabled) {
}

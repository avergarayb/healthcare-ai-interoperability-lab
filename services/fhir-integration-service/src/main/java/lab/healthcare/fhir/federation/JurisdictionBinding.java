package lab.healthcare.fhir.federation;

/**
 * Closed identifier for one server-selected jurisdiction source.
 * The browser and the model do not supply this binding.
 */
public record JurisdictionBinding(String identifierSystem, String identifierValue, String logicalId) {
}

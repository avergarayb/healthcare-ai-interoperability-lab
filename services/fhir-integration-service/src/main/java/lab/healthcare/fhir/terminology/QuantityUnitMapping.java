package lab.healthcare.fhir.terminology;

/**
 * One explicit unit translation. {@code unitText} is the readable Quantity.unit.
 * {@code code} is the UCUM code. {@code mapSetVersion} versions this map set,
 * not the UCUM specification.
 */
public record QuantityUnitMapping(
        String integrationId,
        String sourceUnit,
        String unitText,
        String system,
        String code,
        String mapSetVersion) {
}

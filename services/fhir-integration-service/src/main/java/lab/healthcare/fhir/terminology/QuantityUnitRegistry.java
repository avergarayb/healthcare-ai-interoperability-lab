package lab.healthcare.fhir.terminology;

import java.util.Optional;

/**
 * Resolves a proprietary unit for one integration.
 * An unknown unit is absent. It is not rejected and it is not guessed.
 */
public interface QuantityUnitRegistry {

    String mapSetVersion();

    Optional<QuantityUnitMapping> find(String integrationId, String sourceUnit);
}

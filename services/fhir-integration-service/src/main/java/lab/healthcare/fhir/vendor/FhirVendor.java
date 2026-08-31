package lab.healthcare.fhir.vendor;

import java.util.Locale;

/**
 * Bounded vendor identity for a FHIR destination. Descriptive metadata, not a
 * business-logic switch.
 */
public enum FhirVendor {
    GENERIC,
    EPIC,
    ORACLE_HEALTH;

    public static FhirVendor fromConfiguration(String value) {
        if (value == null || value.isBlank()) {
            return GENERIC;
        }
        String normalized = value.trim().toUpperCase(Locale.ROOT).replace('-', '_');
        try {
            return FhirVendor.valueOf(normalized);
        } catch (IllegalArgumentException ex) {
            throw new IllegalStateException("Unsupported FHIR vendor '" + value + "'", ex);
        }
    }
}

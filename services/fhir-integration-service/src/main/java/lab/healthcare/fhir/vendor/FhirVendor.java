package lab.healthcare.fhir.vendor;

import java.util.Locale;

/**
 * Bounded vendor identity for a FHIR destination. Descriptive metadata, not a
 * business-logic switch. Oracle Health is not represented until its own task.
 */
public enum FhirVendor {
    GENERIC,
    EPIC;

    public static FhirVendor fromConfiguration(String value) {
        if (value == null || value.isBlank()) {
            return GENERIC;
        }
        try {
            return FhirVendor.valueOf(value.trim().toUpperCase(Locale.ROOT));
        } catch (IllegalArgumentException ex) {
            throw new IllegalStateException("Unsupported FHIR vendor '" + value + "'", ex);
        }
    }
}

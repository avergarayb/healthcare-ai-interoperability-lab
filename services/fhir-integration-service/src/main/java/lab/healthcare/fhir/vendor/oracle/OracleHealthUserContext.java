package lab.healthcare.fhir.vendor.oracle;

import java.util.Locale;

/**
 * Primary user type as registration metadata. Access is still determined by
 * scopes and app registration, not by this enum alone.
 */
public enum OracleHealthUserContext {
    PATIENT,
    CLINICIAN_STAFF;

    static OracleHealthUserContext fromConfiguration(String value) {
        if (value == null || value.isBlank()) {
            return PATIENT;
        }
        String normalized = value.trim().toUpperCase(Locale.ROOT).replace('-', '_');
        return valueOf(normalized);
    }
}

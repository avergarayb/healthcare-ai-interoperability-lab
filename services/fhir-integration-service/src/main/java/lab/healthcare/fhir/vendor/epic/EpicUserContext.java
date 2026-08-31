package lab.healthcare.fhir.vendor.epic;

import java.util.Locale;

/**
 * Epic application primary user type as registration metadata.
 * Access is still determined by scopes and app registration, not by this enum alone.
 */
public enum EpicUserContext {
    PATIENT,
    CLINICIAN_STAFF;

    static EpicUserContext fromConfiguration(String value) {
        if (value == null || value.isBlank()) {
            return PATIENT;
        }
        String normalized = value.trim().toUpperCase(Locale.ROOT).replace('-', '_');
        return valueOf(normalized);
    }
}

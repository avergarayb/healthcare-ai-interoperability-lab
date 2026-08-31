package lab.healthcare.fhir.vendor.oracle;

import java.util.Locale;

/**
 * Launch distinction for readiness only. EHR launch is not implemented.
 */
public enum OracleHealthLaunchMode {
    STANDALONE,
    EHR_LAUNCH;

    static OracleHealthLaunchMode fromConfiguration(String value) {
        if (value == null || value.isBlank()) {
            return STANDALONE;
        }
        String normalized = value.trim().toUpperCase(Locale.ROOT).replace('-', '_');
        return valueOf(normalized);
    }
}

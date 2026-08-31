package lab.healthcare.fhir.vendor.epic;

import java.util.Locale;

/**
 * Launch distinction for readiness only. EHR launch is not a Hyperspace implementation.
 */
public enum EpicLaunchMode {
    STANDALONE,
    EHR_LAUNCH;

    static EpicLaunchMode fromConfiguration(String value) {
        if (value == null || value.isBlank()) {
            return STANDALONE;
        }
        String normalized = value.trim().toUpperCase(Locale.ROOT).replace('-', '_');
        return valueOf(normalized);
    }
}

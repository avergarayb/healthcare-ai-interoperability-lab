package lab.healthcare.fhir.vendor.epic;

import java.util.Locale;

public enum EpicEnvironment {
    SANDBOX,
    PRODUCTION;

    static EpicEnvironment fromConfiguration(String value) {
        if (value == null || value.isBlank()) {
            return SANDBOX;
        }
        return valueOf(value.trim().toUpperCase(Locale.ROOT));
    }
}

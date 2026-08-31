package lab.healthcare.fhir.vendor.oracle;

import java.util.Locale;

public enum OracleHealthEnvironment {
    SANDBOX,
    PRODUCTION;

    static OracleHealthEnvironment fromConfiguration(String value) {
        if (value == null || value.isBlank()) {
            return SANDBOX;
        }
        return valueOf(value.trim().toUpperCase(Locale.ROOT));
    }
}

package lab.healthcare.fhir.server;

import java.util.Locale;

/**
 * Where a destination is intended to run. Configuration identity, not a
 * Java switch for FHIR operations.
 */
public enum FhirDeploymentEnvironment {
    LOCAL,
    SYNTHETIC,
    SANDBOX,
    PRODUCTION;

    public static FhirDeploymentEnvironment fromConfiguration(String value) {
        if (value == null || value.isBlank()) {
            return LOCAL;
        }
        return valueOf(value.trim().toUpperCase(Locale.ROOT));
    }
}

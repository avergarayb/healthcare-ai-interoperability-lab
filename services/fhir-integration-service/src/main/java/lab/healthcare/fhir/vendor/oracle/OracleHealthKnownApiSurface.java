package lab.healthcare.fhir.vendor.oracle;

/**
 * Placeholder for vendor-known Oracle Health API catalog information.
 * This lab does not hardcode that catalog. Runtime {@code CapabilityStatement}
 * inspection belongs to a later discovery task.
 */
public final class OracleHealthKnownApiSurface {

    private OracleHealthKnownApiSurface() {
    }

    public static boolean assumesEveryR4Resource() {
        return false;
    }
}

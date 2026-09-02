package lab.healthcare.fhir.vendor.oracle;

/**
 * Placeholder for vendor-known Oracle Health API catalog information.
 * This lab does not hardcode that catalog. Runtime {@code CapabilityStatement}
 * inspection uses {@link lab.healthcare.fhir.capability.FhirCapabilityDiscoveryService}
 * via {@link OracleSandboxCapabilityDiscoveryService}.
 */
public final class OracleHealthKnownApiSurface {

    private OracleHealthKnownApiSurface() {
    }

    public static boolean assumesEveryR4Resource() {
        return false;
    }
}

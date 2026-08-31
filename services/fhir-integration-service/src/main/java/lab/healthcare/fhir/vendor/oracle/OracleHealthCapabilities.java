package lab.healthcare.fhir.vendor.oracle;

/**
 * What this platform currently knows about an Oracle Health integration profile.
 * Readiness is not a certified working sandbox integration.
 */
public record OracleHealthCapabilities(
        boolean supportsSmartAuthorizationCode,
        boolean supportsPkceS256,
        boolean supportsR4,
        boolean supportsStandaloneLaunch,
        boolean supportsEhrLaunchReadiness,
        boolean runtimeSupportsClientAuthentication) {

    public static OracleHealthCapabilities forProfile(
            String fhirVersion,
            OracleHealthLaunchMode launchMode,
            OracleHealthClientAuthentication clientAuthentication) {
        boolean r4 = fhirVersion != null && "R4".equalsIgnoreCase(fhirVersion.trim());
        boolean pkceRuntime = clientAuthentication != null && clientAuthentication.runtimeSupported();
        return new OracleHealthCapabilities(
                pkceRuntime,
                pkceRuntime,
                r4,
                launchMode == OracleHealthLaunchMode.STANDALONE,
                launchMode == OracleHealthLaunchMode.EHR_LAUNCH,
                pkceRuntime);
    }
}

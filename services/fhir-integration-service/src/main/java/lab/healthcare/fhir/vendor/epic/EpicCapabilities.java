package lab.healthcare.fhir.vendor.epic;

/**
 * What this platform currently knows about an Epic integration profile.
 * Readiness is not a certified working sandbox integration.
 */
public record EpicCapabilities(
        boolean supportsSmartAuthorizationCode,
        boolean supportsPkceS256,
        boolean supportsR4,
        boolean supportsStandaloneLaunch,
        boolean supportsEhrLaunchReadiness,
        boolean supportsPersistentAccessReadiness,
        boolean runtimeSupportsClientAuthentication) {

    public static EpicCapabilities forProfile(
            String fhirVersion,
            EpicLaunchMode launchMode,
            EpicClientAuthentication clientAuthentication) {
        boolean r4 = fhirVersion != null && "R4".equalsIgnoreCase(fhirVersion.trim());
        boolean pkceRuntime = clientAuthentication != null && clientAuthentication.runtimeSupported();
        return new EpicCapabilities(
                pkceRuntime,
                pkceRuntime,
                r4,
                launchMode == EpicLaunchMode.STANDALONE,
                launchMode == EpicLaunchMode.EHR_LAUNCH,
                false,
                pkceRuntime);
    }
}

package lab.healthcare.fhir.vendor.epic;

/**
 * Placeholder for vendor-known Epic API catalog information.
 * Epic publishes a resource/API catalog; this lab does not hardcode it.
 * Runtime {@code CapabilityStatement} inspection belongs to a later discovery task.
 */
public final class EpicKnownApiSurface {

    private EpicKnownApiSurface() {
    }

    public static boolean assumesEveryR4Resource() {
        return false;
    }
}

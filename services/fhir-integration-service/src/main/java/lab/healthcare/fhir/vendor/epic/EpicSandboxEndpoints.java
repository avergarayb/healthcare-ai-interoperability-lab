package lab.healthcare.fhir.vendor.epic;

/**
 * Official Epic-hosted non-production sandbox identifiers from public documentation.
 * Configuration still wins if a profile overrides {@code base-url} or discovery.
 *
 * @see <a href="https://fhir.epic.com/Documentation">Epic on FHIR documentation</a>
 */
public final class EpicSandboxEndpoints {

    /**
     * Epic-published R4 sandbox FHIR base URL.
     */
    public static final String FHIR_R4_BASE = "https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/";

    private EpicSandboxEndpoints() {
    }
}

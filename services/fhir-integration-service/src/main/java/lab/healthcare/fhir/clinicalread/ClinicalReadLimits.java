package lab.healthcare.fhir.clinicalread;

public final class ClinicalReadLimits {

    public static final String CONTRACT_VERSION = "clinical-read-v1";
    public static final String DESTINATION = "local-hapi";
    public static final int PAGE_SIZE = 25;
    public static final int MAX_PAGES = 4;
    public static final int MAX_RESOURCES = 100;

    private ClinicalReadLimits() {
    }
}

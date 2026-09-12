package lab.healthcare.fhir.aiconsumerconsent;

/**
 * Abstract non-clinical data scopes. Presence is not permission to read
 * FHIR or clinical records.
 */
public final class ConsumerConsentDataScopes {

    public static final String SUMMARY_METADATA = "SUMMARY_METADATA";
    public static final String NON_CLINICAL_STATUS = "NON_CLINICAL_STATUS";
    public static final String SYNTHETIC_DEMO_CONTEXT = "SYNTHETIC_DEMO_CONTEXT";

    private ConsumerConsentDataScopes() {
    }
}

package lab.healthcare.fhir.agent;

/**
 * Stable operational reason codes. Never include clinical values or vendor
 * names.
 */
public final class AgentReasonCodes {

    public static final String READY_FOR_BOUNDARY = "READY_FOR_BOUNDARY";
    public static final String CONTRACT_MISSING = "CONTRACT_MISSING";
    public static final String CONTRACT_REJECTED = "CONTRACT_REJECTED";
    public static final String PIPELINE_NOT_USABLE = "PIPELINE_NOT_USABLE";
    public static final String PIPELINE_PARTIAL = "PIPELINE_PARTIAL";
    public static final String INSUFFICIENT_CLINICAL_DATA = "INSUFFICIENT_CLINICAL_DATA";

    private AgentReasonCodes() {
    }
}

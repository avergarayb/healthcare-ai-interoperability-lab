package lab.healthcare.fhir.aiconsumerpolicy;

/**
 * Synthetic consumer operations. Only {@link #READ_CONTRACT} is allowed.
 */
public final class AiConsumerPolicyOperations {

    public static final String READ_CONTRACT = "READ_CONTRACT";
    public static final String EXECUTE_MODEL = "EXECUTE_MODEL";
    public static final String GENERATE_CLINICAL_OUTPUT = "GENERATE_CLINICAL_OUTPUT";
    public static final String WRITE_BACK_TO_FHIR = "WRITE_BACK_TO_FHIR";
    public static final String UPDATE_PATIENT = "UPDATE_PATIENT";
    public static final String CREATE_MEDICATION_REQUEST = "CREATE_MEDICATION_REQUEST";
    public static final String DISPATCH_TO_AI_SERVICE = "DISPATCH_TO_AI_SERVICE";

    private AiConsumerPolicyOperations() {
    }
}

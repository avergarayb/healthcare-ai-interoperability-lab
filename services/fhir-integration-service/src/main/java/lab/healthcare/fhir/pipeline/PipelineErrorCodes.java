package lab.healthcare.fhir.pipeline;

/**
 * Stable vendor-neutral error codes. Do not add Epic* or Oracle* codes.
 */
public final class PipelineErrorCodes {

    public static final String FHIR_TIMEOUT = "FHIR_TIMEOUT";
    public static final String FHIR_AUTHENTICATION_FAILED = "FHIR_AUTHENTICATION_FAILED";
    public static final String FHIR_PROVIDER_ERROR = "FHIR_PROVIDER_ERROR";
    public static final String FHIR_RESPONSE_INVALID = "FHIR_RESPONSE_INVALID";
    public static final String FHIR_NOT_AVAILABLE = "FHIR_NOT_AVAILABLE";
    public static final String PROJECTION_VALIDATION_FAILED = "PROJECTION_VALIDATION_FAILED";
    public static final String MODEL_BOUNDARY_REJECTED = "MODEL_BOUNDARY_REJECTED";
    public static final String AGENT_STUB_REJECTED = "AGENT_STUB_REJECTED";

    private PipelineErrorCodes() {
    }
}

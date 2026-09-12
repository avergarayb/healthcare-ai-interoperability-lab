package lab.healthcare.fhir.aigateway;

/**
 * Stable execution-gate reason codes. Never include clinical values or vendor
 * names.
 */
public final class AiExecutionReasonCodes {

    public static final String ELIGIBLE_BUT_NOT_AUTHORIZED = "ELIGIBLE_BUT_NOT_AUTHORIZED";
    public static final String NOT_ELIGIBLE = "NOT_ELIGIBLE";
    public static final String PREMATURE_MODEL_AUTHORIZATION = "PREMATURE_MODEL_AUTHORIZATION";

    private AiExecutionReasonCodes() {
    }
}

package lab.healthcare.fhir.vendor.oracle;

/**
 * How complete this Oracle Health profile is. Not a certification claim.
 */
public enum OracleHealthReadinessState {
    NOT_CONFIGURED,
    CONFIGURED,
    SMART_COMPATIBLE,
    READY_FOR_SANDBOX
}

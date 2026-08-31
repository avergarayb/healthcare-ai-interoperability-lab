package lab.healthcare.fhir.vendor.epic;

/**
 * How complete this Epic profile is. Not a certification claim.
 */
public enum EpicReadinessState {
    NOT_CONFIGURED,
    CONFIGURED,
    SMART_COMPATIBLE,
    READY_FOR_SANDBOX
}

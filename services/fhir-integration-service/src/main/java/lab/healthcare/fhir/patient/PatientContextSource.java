package lab.healthcare.fhir.patient;

/**
 * How a laboratory Patient context was selected. Not a SMART claim and not a
 * FHIR search result.
 */
public enum PatientContextSource {
    CONFIGURED,
    SMART_LAUNCH,
    APPLICATION_SELECTED
}

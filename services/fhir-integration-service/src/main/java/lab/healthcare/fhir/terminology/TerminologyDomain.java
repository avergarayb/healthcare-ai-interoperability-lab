package lab.healthcare.fhir.terminology;

/**
 * The FHIR element a proprietary code is translated into.
 * A code is valid in only one domain.
 */
public enum TerminologyDomain {
    ENCOUNTER_STATUS,
    ENCOUNTER_CLASS,
    OBSERVATION_STATUS,
    OBSERVATION_CATEGORY,
    APPOINTMENT_STATUS
}

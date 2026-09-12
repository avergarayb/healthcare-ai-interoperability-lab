package lab.healthcare.fhir.aiconsumerscope;

/**
 * Declarative purpose-to-scope relationship. Declared is not verified
 * and is not approved.
 */
public enum PurposeScopeAlignmentStatus {
    NOT_DECLARED,
    DECLARED_NOT_VERIFIED,
    REQUIRES_HUMAN_REVIEW
}

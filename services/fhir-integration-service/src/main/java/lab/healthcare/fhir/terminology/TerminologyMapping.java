package lab.healthcare.fhir.terminology;

/**
 * One explicit translation. {@code targetSystem} is present only when the
 * FHIR element is a Coding. Status codes have no system.
 * {@code mapSetVersion} versions this map set, not an external terminology.
 */
public record TerminologyMapping(
        String integrationId,
        TerminologyDomain domain,
        String sourceCode,
        String targetCode,
        String targetSystem,
        String mapSetVersion) {
}

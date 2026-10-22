package lab.healthcare.fhir.terminology;

/**
 * Resolves one proprietary code for one integration and domain.
 * An unknown integration, domain, or source code is rejected.
 */
public interface TerminologyRegistry {

    String mapSetVersion();

    TerminologyMapping resolve(String integrationId, TerminologyDomain domain, String sourceCode);
}

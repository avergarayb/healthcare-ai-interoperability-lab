package lab.healthcare.fhir.terminology;

/**
 * The registry has no explicit mapping for the requested integration, domain, and source code.
 */
public final class TerminologyMappingNotFound extends RuntimeException {

    public TerminologyMappingNotFound(String integrationId, TerminologyDomain domain, String sourceCode) {
        super("No terminology mapping for " + integrationId + " " + domain + " " + sourceCode);
    }
}

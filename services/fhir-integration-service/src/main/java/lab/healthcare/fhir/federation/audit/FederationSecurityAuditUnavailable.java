package lab.healthcare.fhir.federation.audit;

/** Raised when the mandatory federation access decision cannot be persisted. */
public final class FederationSecurityAuditUnavailable extends RuntimeException {

    public FederationSecurityAuditUnavailable() {
        super("Federation security audit is unavailable");
    }

    public FederationSecurityAuditUnavailable(Throwable cause) {
        super("Federation security audit is unavailable", cause);
    }
}

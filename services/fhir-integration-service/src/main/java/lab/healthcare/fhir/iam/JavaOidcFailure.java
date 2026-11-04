package lab.healthcare.fhir.iam;

/** Closed server codes only; causes and upstream bodies never become HTTP/log output. */
final class JavaOidcFailure extends RuntimeException {
    final String reason;
    final int status;
    JavaOidcFailure(String reason, int status) {
        super(reason, null, false, false);
        this.reason = reason;
        this.status = status;
    }
}

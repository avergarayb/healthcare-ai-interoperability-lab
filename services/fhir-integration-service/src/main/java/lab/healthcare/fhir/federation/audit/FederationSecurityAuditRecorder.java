package lab.healthcare.fhir.federation.audit;

@FunctionalInterface
public interface FederationSecurityAuditRecorder {

    void append(FederationSecurityAuditEvent event);
}

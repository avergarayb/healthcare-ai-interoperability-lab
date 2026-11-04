package lab.healthcare.fhir.iam;

import java.time.Instant;
import java.util.List;
import java.util.Map;

/** Request-local only. Never serialize this full internal record or forward it as authority. */
record JavaPrincipalContext(String internalPrincipalId, String organizationId, String providerId,
        String externalIssuer, String externalSubject, Instant authenticatedAt, Instant expiresAt,
        String correlationId) {
    String contextVersion() { return "identity-principal-context-v1"; }
    String principalType() { return "workload"; }
    String authenticationMethod() { return "oauth2_client_credentials"; }
    String audience() { return JavaOidcTrust.AUDIENCE; }
    List<String> effectivePermissions() { return List.of(JavaOidcTrust.PERMISSION); }
    Map<String, Object> projection() {
        return Map.ofEntries(Map.entry("context_version", contextVersion()), Map.entry("internal_principal_id", internalPrincipalId),
                Map.entry("organization_id", organizationId), Map.entry("principal_type", principalType()),
                Map.entry("authentication_method", authenticationMethod()), Map.entry("audience", audience()),
                Map.entry("effective_permissions", effectivePermissions()), Map.entry("authenticated_at", authenticatedAt.toString()),
                Map.entry("expires_at", expiresAt.toString()), Map.entry("correlation_id", correlationId));
    }
    @Override public String toString() { return "JavaPrincipalContext[redacted]"; }
}

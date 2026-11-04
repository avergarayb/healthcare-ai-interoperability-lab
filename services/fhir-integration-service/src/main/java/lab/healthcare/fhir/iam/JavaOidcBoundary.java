package lab.healthcare.fhir.iam;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.time.Clock;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.slf4j.LoggerFactory;
import org.springframework.web.filter.OncePerRequestFilter;

/** One bounded technical GET boundary; no clinical/graph/connector imports. */
final class JavaOidcBoundary extends OncePerRequestFilter {
    static final String CONTEXT = "iam.java.workload.context.v1";
    private JavaOidcTrust trust;
    private JavaWorkloadVerifier verifier;
    private JavaOidcAudit audit;
    private final Clock clock;

    JavaOidcBoundary(String trustPath, String auditPath, List<String> forbidden) {
        clock = Clock.systemUTC();
        try { audit = new JavaOidcAudit(auditPath, forbidden); } catch (JavaOidcFailure ignored) { }
        try {
            trust = JavaOidcTrust.load(trustPath);
            verifier = new JavaWorkloadVerifier(trust, new BoundedOidcKeys(trust), clock);
        } catch (JavaOidcFailure ignored) { }
    }
    JavaOidcBoundary(JavaOidcTrust trust, JavaWorkloadVerifier verifier, JavaOidcAudit audit, Clock clock) {
        this.trust = trust; this.verifier = verifier; this.audit = audit; this.clock = clock;
    }
    @Override protected boolean shouldNotFilter(HttpServletRequest request) {
        return !matches(request);
    }
    static boolean matches(HttpServletRequest request) {
        return "GET".equals(request.getMethod())
                && JavaOidcTrust.ROUTE.equals(request.getRequestURI().substring(request.getContextPath().length()));
    }
    static List<String> headers(HttpServletRequest request, String name) {
        return Collections.list(request.getHeaders(name));
    }
    private static String credential(HttpServletRequest request) {
        if (!headers(request, "X-Service-Token").isEmpty() || !headers(request, "Cookie").isEmpty()) {
            throw new JavaOidcFailure("credential_conflict", 401);
        }
        List<String> values = headers(request, "Authorization");
        if (values.isEmpty()) { throw new JavaOidcFailure("credential_missing", 401); }
        if (values.size() != 1) { throw new JavaOidcFailure("credential_ambiguous", 401); }
        String value = values.getFirst();
        if (value.length() > 16391 || !value.matches("Bearer [A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+")) {
            throw new JavaOidcFailure("credential_malformed", 401);
        }
        return value.substring(7);
    }
    private JavaPrincipalContext resolve(String token, HttpServletRequest request, String correlation) {
        if (trust == null || verifier == null) { throw new JavaOidcFailure("configuration_incomplete", 503); }
        var verified = verifier.verify(token);
        var binding = trust.bindings().stream().filter(b -> b.clientId().equals(verified.clientId())
                && b.externalSubject().equals(verified.subject())).findFirst()
                .orElseThrow(() -> new JavaOidcFailure("binding_unknown", 401));
        if (!binding.bindingEnabled()) { throw new JavaOidcFailure("binding_disabled", 401); }
        if (!binding.principalEnabled()) { throw new JavaOidcFailure("principal_disabled", 401); }
        List<String> candidates = headers(request, "X-IAM-Lab-Organization");
        if (!binding.membershipEnabled() || !trust.allowedOrganizationIds().contains(binding.organizationId())
                || candidates.size() > 1 || (!candidates.isEmpty()
                    && (!JavaOidcTrust.id(candidates.getFirst()) || !binding.organizationId().equals(candidates.getFirst())))) {
            throw new JavaOidcFailure("organization_rejected", 403);
        }
        if (!binding.permissions().contains(JavaOidcTrust.PERMISSION)) { throw new JavaOidcFailure("policy_rejected", 403); }
        if (!verified.expiresAt().isAfter(clock.instant())) { throw new JavaOidcFailure("token_expired", 401); }
        return new JavaPrincipalContext(binding.internalPrincipalId(), binding.organizationId(), trust.providerId(),
                trust.issuer(), verified.subject(), clock.instant(), verified.expiresAt(), correlation);
    }
    @Override protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws IOException, ServletException {
        String correlation = correlation(request);
        JavaPrincipalContext context = null;
        int status = 200;
        String reason = "access_granted";
        try { context = resolve(credential(request), request, correlation); }
        catch (JavaOidcFailure failure) { status = failure.status; reason = failure.reason; }
        catch (RuntimeException failure) { status = 503; reason = "configuration_incomplete"; }
        try {
            if (audit == null) { throw new JavaOidcFailure("audit_unavailable", 503); }
            audit.append(reason, correlation, trust == null ? null : trust.providerId(), context);
        } catch (JavaOidcFailure unavailable) {
            status = 503; context = null;
            LoggerFactory.getLogger(JavaOidcBoundary.class).warn("java_oidc_audit_unavailable correlation={}", correlation);
        }
        if (context != null && !context.expiresAt().isAfter(clock.instant())) { status = 401; context = null; }
        response.setHeader("Cache-Control", "no-store");
        response.setHeader("X-Correlation-ID", correlation);
        if (status != 200) {
            if (status == 401) { response.setHeader("WWW-Authenticate", "Bearer"); }
            response.setStatus(status); response.setContentType("application/json");
            JavaOidcTrust.JSON.writeValue(response.getOutputStream(), Map.of("error",
                    status == 401 ? "unauthorized" : status == 403 ? "forbidden" : "unavailable"));
            return;
        }
        request.setAttribute(CONTEXT, context);
        try { chain.doFilter(request, response); }
        finally { request.removeAttribute(CONTEXT); }
    }
    private static String correlation(HttpServletRequest request) {
        List<String> values = headers(request, "X-Correlation-ID");
        if (values.size() == 1 && values.getFirst().length() == 36) {
            try {
                UUID id = UUID.fromString(values.getFirst());
                if (id.version() == 4 && id.toString().equals(values.getFirst())) { return id.toString(); }
            } catch (IllegalArgumentException ignored) { }
        }
        return UUID.randomUUID().toString();
    }
}

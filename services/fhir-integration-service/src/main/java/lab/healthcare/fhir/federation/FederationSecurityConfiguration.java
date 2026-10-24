package lab.healthcare.fhir.federation;

import lab.healthcare.fhir.federation.audit.FederationSecurityAudit;
import lab.healthcare.fhir.federation.audit.FederationSecurityAuditUnavailable;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.web.servlet.FilterRegistrationBean;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.Ordered;
import org.springframework.http.HttpStatus;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Enumeration;
import java.util.LinkedHashMap;
import java.util.Map;

@Configuration
public class FederationSecurityConfiguration {

    static final String CALLER_ATTRIBUTE = "federation.caller";

    @Bean
    FilterRegistrationBean<FederationParticipantFilter> federationParticipantFilter(
            FederationProperties properties, FederationSecurityAudit securityAudit) {
        FilterRegistrationBean<FederationParticipantFilter> registration = new FilterRegistrationBean<>();
        registration.setFilter(new FederationParticipantFilter(tokens(properties), securityAudit));
        registration.addUrlPatterns("/api/clinical-federation/v1/*");
        registration.setOrder(Ordered.HIGHEST_PRECEDENCE);
        return registration;
    }

    private static Map<String, String> tokens(FederationProperties properties) {
        Map<String, String> tokens = new LinkedHashMap<>();
        properties.getParticipants().forEach((key, participant) -> {
            if (participant != null && participant.getServiceToken() != null && !participant.getServiceToken().isBlank()) {
                if (tokens.containsValue(participant.getServiceToken())) {
                    throw new IllegalStateException("Federation participant tokens must be distinct");
                }
                tokens.put(key, participant.getServiceToken());
            }
        });
        return Map.copyOf(tokens);
    }

    static final class FederationParticipantFilter extends OncePerRequestFilter {

        private static final Logger log = LoggerFactory.getLogger(FederationParticipantFilter.class);
        private final Map<String, String> tokens;
        private final FederationSecurityAudit securityAudit;

        FederationParticipantFilter(Map<String, String> tokens, FederationSecurityAudit securityAudit) {
            this.tokens = tokens;
            this.securityAudit = securityAudit;
        }

        @Override
        protected boolean shouldNotFilter(HttpServletRequest request) {
            String uri = request.getRequestURI();
            return uri == null || !uri.startsWith("/api/clinical-federation/v1/");
        }

        @Override
        protected void doFilterInternal(
                HttpServletRequest request, HttpServletResponse response, FilterChain filterChain)
                throws ServletException, IOException {
            Enumeration<String> values = request.getHeaders("X-Service-Token");
            String presented = values != null && values.hasMoreElements() ? values.nextElement() : null;
            boolean duplicate = values != null && values.hasMoreElements();
            String caller = duplicate ? null : match(presented);
            if (caller != null) {
                request.setAttribute(CALLER_ATTRIBUTE, caller);
                filterChain.doFilter(request, response);
                return;
            }
            String reason = tokens.isEmpty()
                    ? "participant_authentication_unconfigured"
                    : presented == null || presented.isBlank()
                            ? "participant_token_missing"
                            : "participant_token_invalid";
            try {
                securityAudit.authenticationDenied(reason);
            } catch (FederationSecurityAuditUnavailable ex) {
                log.error("federation_security_audit_unavailable decision=authentication_denied", ex);
                response.setStatus(HttpStatus.SERVICE_UNAVAILABLE.value());
                return;
            }
            log.info("federation_authentication_rejected reason={}", reason);
            response.setStatus(HttpStatus.UNAUTHORIZED.value());
        }

        private String match(String presented) {
            if (presented == null || presented.isBlank()) {
                return null;
            }
            byte[] right = presented.getBytes(StandardCharsets.UTF_8);
            for (Map.Entry<String, String> entry : tokens.entrySet()) {
                byte[] left = entry.getValue().getBytes(StandardCharsets.UTF_8);
                if (MessageDigest.isEqual(left, right)) {
                    return entry.getKey();
                }
            }
            return null;
        }
    }
}

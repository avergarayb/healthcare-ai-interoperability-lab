package lab.healthcare.fhir.federation;

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
import java.util.LinkedHashMap;
import java.util.Map;

@Configuration
public class FederationSecurityConfiguration {

    static final String CALLER_ATTRIBUTE = "federation.caller";

    @Bean
    FilterRegistrationBean<FederationParticipantFilter> federationParticipantFilter(FederationProperties properties) {
        FilterRegistrationBean<FederationParticipantFilter> registration = new FilterRegistrationBean<>();
        registration.setFilter(new FederationParticipantFilter(tokens(properties)));
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

        FederationParticipantFilter(Map<String, String> tokens) {
            this.tokens = tokens;
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
            String presented = request.getHeader("X-Service-Token");
            String caller = match(presented);
            if (caller != null) {
                request.setAttribute(CALLER_ATTRIBUTE, caller);
                filterChain.doFilter(request, response);
                return;
            }
            String reason = tokens.isEmpty() ? "unconfigured" : presented == null || presented.isBlank() ? "absent" : "mismatch";
            log.info("federation_authentication_rejected reason={}", reason);
            response.setStatus(HttpStatus.UNAUTHORIZED.value());
        }

        private String match(String presented) {
            if (presented == null || presented.isBlank()) {
                return null;
            }
            byte[] right = presented.trim().getBytes(StandardCharsets.UTF_8);
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

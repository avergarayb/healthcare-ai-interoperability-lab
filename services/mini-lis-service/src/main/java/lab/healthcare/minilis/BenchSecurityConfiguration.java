package lab.healthcare.minilis;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.servlet.http.HttpSession;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.annotation.Order;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.core.Authentication;
import org.springframework.security.oauth2.client.registration.ClientRegistration;
import org.springframework.security.oauth2.client.registration.ClientRegistrationRepository;
import org.springframework.security.oauth2.client.registration.ClientRegistrations;
import org.springframework.security.oauth2.client.registration.InMemoryClientRegistrationRepository;
import org.springframework.security.oauth2.core.AuthorizationGrantType;
import org.springframework.security.oauth2.core.ClientAuthenticationMethod;
import org.springframework.security.oauth2.core.oidc.user.OidcUser;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.csrf.HttpSessionCsrfTokenRepository;

import java.io.InputStream;
import java.time.Instant;
import java.util.Date;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

@Configuration
@EnableWebSecurity
public class BenchSecurityConfiguration {
    private static final Set<String> ROLES = Set.of("receptionist", "lab-technician", "lab-validator", "auditor");
    private static final ObjectMapper JSON = new ObjectMapper();

    @Bean
    @Order(1)
    @ConditionalOnProperty(name = "mini-lis.oidc.client-enabled", havingValue = "true")
    SecurityFilterChain benchOidc(
            HttpSecurity http,
            @Value("${mini-lis.oidc.issuer}") String issuer,
            @Value("${mini-lis.oidc.audience}") String audience) throws Exception {
        Map<String, String> roles = bindings();
        http.securityMatcher("/bench/**", "/oauth2/**", "/login/**", "/logout")
                .authorizeHttpRequests(auth -> auth.requestMatchers("/bench/login", "/login/**", "/oauth2/**").permitAll().anyRequest().authenticated())
                .oauth2Login(oauth -> oauth.successHandler((request, response, authentication) -> accept(request, response, authentication, roles, issuer, audience)))
                .logout(logout -> logout.logoutUrl("/logout").invalidateHttpSession(true).deleteCookies("JSESSIONID"))
                .sessionManagement(session -> session.sessionFixation().changeSessionId())
                .csrf(csrf -> {
                    HttpSessionCsrfTokenRepository repository = new HttpSessionCsrfTokenRepository();
                    repository.setParameterName("csrf");
                    csrf.csrfTokenRepository(repository);
                });
        return http.build();
    }

    @Bean
    @Order(2)
    @ConditionalOnProperty(name = "mini-lis.oidc.client-enabled", havingValue = "true")
    SecurityFilterChain benchServices(HttpSecurity http) throws Exception {
        http.authorizeHttpRequests(auth -> auth.anyRequest().permitAll()).csrf(csrf -> csrf.disable());
        return http.build();
    }

    @Bean
    @ConditionalOnProperty(name = "mini-lis.oidc.client-enabled", havingValue = "false", matchIfMissing = true)
    SecurityFilterChain laboratorySession(HttpSecurity http) throws Exception {
        http.authorizeHttpRequests(auth -> auth.anyRequest().permitAll()).csrf(csrf -> csrf.disable());
        return http.build();
    }

    @Bean
    @ConditionalOnProperty(name = "mini-lis.oidc.client-enabled", havingValue = "true")
    ClientRegistrationRepository benchClients(
            @Value("${mini-lis.oidc.issuer}") String issuer,
            @Value("${mini-lis.oidc.client-id:mini-lis-web}") String clientId) {
        return new InMemoryClientRegistrationRepository(ClientRegistrations.fromIssuerLocation(issuer)
                .registrationId("bench")
                .clientId(clientId)
                .clientAuthenticationMethod(ClientAuthenticationMethod.NONE)
                .redirectUri("{baseUrl}/login/oauth2/code/{registrationId}")
                .scope("openid", "profile")
                .clientSettings(ClientRegistration.ClientSettings.builder().requireProofKey(true).build())
                .build());
    }

    private static void accept(
            HttpServletRequest request, HttpServletResponse response, Authentication authentication,
            Map<String, String> roles, String issuer, String audience) throws java.io.IOException {
        if (!(authentication.getPrincipal() instanceof OidcUser user) || !issuer.equals(user.getClaim("iss"))) {
            response.sendRedirect("/bench/login?aviso=no-autorizado");
            return;
        }
        Object aud = user.getClaim("aud");
        boolean audienceOk = audience.equals(aud) || (aud instanceof List<?> values && values.contains(audience));
        Instant expires = expiry(user.getClaim("exp"));
        String username = user.getClaim("preferred_username");
        String role = username == null ? null : roles.get(username);
        if (!audienceOk || expires == null || !expires.isAfter(Instant.now()) || role == null || !ROLES.contains(role)
                || !"org-mini-his".equals(user.getClaim("organization")) || !realmRoles(user).contains(role)) {
            response.sendRedirect("/bench/login?aviso=no-autorizado");
            return;
        }
        HttpSession session = request.getSession(true);
        session.setAttribute("benchPrincipal", new BenchController.BenchPrincipal(
                username, "lab-validator".equals(role), role, "org-mini-his", "oidc"));
        session.setAttribute("csrf", UUID.randomUUID().toString());
        response.sendRedirect("/bench/orders");
    }

    private static Map<String, String> bindings() throws java.io.IOException {
        try (InputStream input = BenchSecurityConfiguration.class.getResourceAsStream("/hospital-bindings.json")) {
            JsonNode root = input == null ? null : JSON.readTree(input);
            java.util.LinkedHashMap<String, String> bindings = new java.util.LinkedHashMap<>();
            if (root != null) {
                root.fields().forEachRemaining(entry -> bindings.put(entry.getKey(), entry.getValue().path("role").asText("")));
            }
            return Map.copyOf(bindings);
        }
    }

    private static Instant expiry(Object value) {
        if (value instanceof Instant instant) return instant;
        if (value instanceof Date date) return date.toInstant();
        if (value instanceof Number number) return Instant.ofEpochSecond(number.longValue());
        return null;
    }

    private static List<?> realmRoles(OidcUser user) {
        Object access = user.getClaim("realm_access");
        if (access instanceof Map<?, ?> map && map.get("roles") instanceof List<?> roles) {
            return roles;
        }
        return List.of();
    }
}

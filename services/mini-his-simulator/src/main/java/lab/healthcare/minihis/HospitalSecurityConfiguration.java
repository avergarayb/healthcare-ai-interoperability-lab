package lab.healthcare.minihis;

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
import org.springframework.security.oauth2.client.OAuth2AuthorizedClient;
import org.springframework.security.oauth2.client.authentication.OAuth2AuthenticationToken;
import org.springframework.security.oauth2.client.registration.ClientRegistration;
import org.springframework.security.oauth2.client.registration.ClientRegistrations;
import org.springframework.security.oauth2.client.registration.ClientRegistrationRepository;
import org.springframework.security.oauth2.client.registration.InMemoryClientRegistrationRepository;
import org.springframework.security.oauth2.core.ClientAuthenticationMethod;
import org.springframework.security.oauth2.client.web.OAuth2AuthorizedClientRepository;
import org.springframework.security.oauth2.core.oidc.user.OidcUser;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.AuthenticationSuccessHandler;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.Map;
import java.util.UUID;

@Configuration
@EnableWebSecurity
public class HospitalSecurityConfiguration {

    @Bean
    @Order(1)
    @ConditionalOnProperty(name = "mini-his.oidc.client-enabled", havingValue = "true")
    SecurityFilterChain hospitalOidc(
            HttpSecurity http, ClientRegistrationRepository registrations, OAuth2AuthorizedClientRepository clients,
            SecurityEvents events,
            @Value("${mini-his.oidc.issuer}") String issuer,
            @Value("${mini-his.oidc.audience}") String audience,
            @Value("${mini-his.oidc.bindings:}") String bindingsPath) throws Exception {
        Map<String, HospitalBindings.Binding> bindings = bindingsFrom(bindingsPath);
        http.securityMatcher("/ward/**", "/showcase/**", "/oauth2/**", "/login/**", "/logout")
                .authorizeHttpRequests(auth -> auth
                        .requestMatchers("/ward/login", "/login/**", "/oauth2/**").permitAll()
                        .anyRequest().authenticated())
                .oauth2Login(oauth -> oauth.successHandler(success(bindings, issuer, audience, events, clients)))
                .logout(logout -> logout.logoutUrl("/logout").invalidateHttpSession(true).deleteCookies("JSESSIONID"))
                .sessionManagement(session -> session.sessionFixation().changeSessionId())
                .csrf(csrf -> csrf.disable());
        return http.build();
    }

    @Bean
    @Order(2)
    @ConditionalOnProperty(name = "mini-his.oidc.client-enabled", havingValue = "true")
    SecurityFilterChain hospitalServices(HttpSecurity http) throws Exception {
        http.authorizeHttpRequests(auth -> auth.anyRequest().permitAll())
                .csrf(csrf -> csrf.disable())
                .requestCache(cache -> cache.disable());
        return http.build();
    }

    @Bean
    @ConditionalOnProperty(name = "mini-his.oidc.client-enabled", havingValue = "false", matchIfMissing = true)
    SecurityFilterChain laboratorySession(HttpSecurity http) throws Exception {
        http.authorizeHttpRequests(auth -> auth.anyRequest().permitAll())
                .csrf(csrf -> csrf.disable())
                .requestCache(cache -> cache.disable());
        return http.build();
    }

    @Bean
    @ConditionalOnProperty(name = "mini-his.oidc.client-enabled", havingValue = "true")
    ClientRegistrationRepository hospitalClients(
            @Value("${mini-his.oidc.issuer}") String issuer,
            @Value("${mini-his.oidc.client-id:mini-his-web}") String clientId) {
        ClientRegistration registration = ClientRegistrations.fromIssuerLocation(issuer)
                .registrationId("hospital")
                .clientId(clientId)
                .clientAuthenticationMethod(ClientAuthenticationMethod.NONE)
                .redirectUri("{baseUrl}/login/oauth2/code/{registrationId}")
                .scope("openid", "profile")
                .clientSettings(ClientRegistration.ClientSettings.builder().requireProofKey(true).build())
                .build();
        return new InMemoryClientRegistrationRepository(registration);
    }

    private static AuthenticationSuccessHandler success(
            Map<String, HospitalBindings.Binding> bindings, String issuer, String audience, SecurityEvents events,
            OAuth2AuthorizedClientRepository clients) {
        return (HttpServletRequest request, HttpServletResponse response, Authentication authentication) -> {
            if (!(authentication.getPrincipal() instanceof OidcUser user)) {
                response.sendRedirect("/ward/login?aviso=no-autorizado");
                return;
            }
            try {
                String rawAccess = accessToken(authentication, request, clients);
                Map<String, Object> claims = new java.util.HashMap<>(user.getClaims());
                if (claims.get("aud") == null) {
                    claims.put("aud", user.getAudience());
                }
                if (claims.get("exp") == null && user.getExpiresAt() != null) {
                    claims.put("exp", user.getExpiresAt());
                }
                copyAuthority(claims, rawAccess);
                WardPrincipal principal = HospitalIdentity.accept(
                        claims, bindings, issuer, audience, Instant.now());
                String access = HospitalTokenVerifier.delegation(rawAccess);
                HttpSession session = request.getSession(true);
                session.setAttribute("wardPrincipal", principal);
                session.setAttribute("csrf", UUID.randomUUID().toString());
                if (!access.isBlank()) {
                    session.setAttribute("hospitalAccessToken", access);
                }
                events.record(principal.userId(), principal.role(), principal.organizationId(), "login", "/showcase", "accepted");
                response.sendRedirect("/showcase");
            } catch (HospitalRejection ex) {
                events.record("denied", "", "", "login", "/showcase", ex.code);
                response.sendRedirect("/ward/login?aviso=no-autorizado");
            }
        };
    }

    private static void copyAuthority(Map<String, Object> claims, String accessToken) {
        if (accessToken == null || accessToken.isBlank()) {
            return;
        }
        try {
            var tokenClaims = com.nimbusds.jwt.SignedJWT.parse(accessToken).getJWTClaimsSet();
            Object roles = tokenClaims.getClaim("realm_access");
            Object organization = tokenClaims.getClaim("organization");
            if (roles != null) {
                claims.put("realm_access", roles);
            }
            if (organization != null && claims.get("organization") == null) {
                claims.put("organization", organization);
            }
        } catch (java.text.ParseException ex) {
            claims.remove("realm_access");
        }
    }

    private static String accessToken(
            Authentication authentication, HttpServletRequest request, OAuth2AuthorizedClientRepository clients) {
        if (!(authentication instanceof OAuth2AuthenticationToken oauth)) {
            return "";
        }
        OAuth2AuthorizedClient client = clients.loadAuthorizedClient(
                oauth.getAuthorizedClientRegistrationId(), authentication, request);
        if (client == null || client.getAccessToken() == null) {
            return "";
        }
        return client.getAccessToken().getTokenValue();
    }

    private static Map<String, HospitalBindings.Binding> bindingsFrom(String path) throws IOException {
        if (path == null || path.isBlank()) {
            try (var input = HospitalSecurityConfiguration.class.getResourceAsStream("/hospital-bindings.json")) {
                return input == null ? Map.of() : HospitalBindings.load(input);
            }
        }
        try (var input = Files.newInputStream(Path.of(path))) {
            return HospitalBindings.load(input);
        }
    }
}

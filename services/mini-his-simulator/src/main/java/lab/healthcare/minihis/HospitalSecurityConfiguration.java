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
import org.springframework.security.oauth2.client.registration.ClientRegistration;
import org.springframework.security.oauth2.client.registration.ClientRegistrationRepository;
import org.springframework.security.oauth2.client.registration.InMemoryClientRegistrationRepository;
import org.springframework.security.oauth2.core.AuthorizationGrantType;
import org.springframework.security.oauth2.core.ClientAuthenticationMethod;
import org.springframework.security.oauth2.core.oidc.user.OidcUser;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.AuthenticationSuccessHandler;
import org.springframework.security.web.csrf.HttpSessionCsrfTokenRepository;

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
            HttpSecurity http, ClientRegistrationRepository registrations, SecurityEvents events,
            @Value("${mini-his.oidc.issuer}") String issuer,
            @Value("${mini-his.oidc.audience}") String audience,
            @Value("${mini-his.oidc.bindings:}") String bindingsPath) throws Exception {
        Map<String, HospitalBindings.Binding> bindings = bindingsFrom(bindingsPath);
        http.securityMatcher("/ward/**", "/showcase/**", "/oauth2/**", "/login/**", "/logout")
                .authorizeHttpRequests(auth -> auth
                        .requestMatchers("/ward/login", "/login/**", "/oauth2/**").permitAll()
                        .anyRequest().authenticated())
                .oauth2Login(oauth -> oauth.successHandler(success(bindings, issuer, audience, events)))
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
        ClientRegistration registration = ClientRegistration.withRegistrationId("hospital")
                .clientId(clientId)
                .clientAuthenticationMethod(ClientAuthenticationMethod.NONE)
                .authorizationGrantType(AuthorizationGrantType.AUTHORIZATION_CODE)
                .redirectUri("{baseUrl}/login/oauth2/code/{registrationId}")
                .scope("openid")
                .issuerUri(issuer)
                .clientSettings(ClientRegistration.ClientSettings.builder().requireProofKey(true).build())
                .build();
        return new InMemoryClientRegistrationRepository(registration);
    }

    private static AuthenticationSuccessHandler success(
            Map<String, HospitalBindings.Binding> bindings, String issuer, String audience, SecurityEvents events) {
        return (HttpServletRequest request, HttpServletResponse response, Authentication authentication) -> {
            if (!(authentication.getPrincipal() instanceof OidcUser user)) {
                response.sendRedirect("/ward/login?aviso=no-autorizado");
                return;
            }
            try {
                WardPrincipal principal = HospitalIdentity.accept(
                        user.getClaims(), bindings, issuer, audience, Instant.now());
                HttpSession previous = request.getSession(false);
                if (previous != null) {
                    previous.invalidate();
                }
                HttpSession session = request.getSession(true);
                session.setAttribute("wardPrincipal", principal);
                session.setAttribute("csrf", UUID.randomUUID().toString());
                String token = user.getIdToken().getTokenValue();
                if (token != null && token.length() <= 4000 && token.chars().filter(ch -> ch == '.').count() == 2) {
                    session.setAttribute("hospitalIdToken", token);
                }
                events.record(principal.userId(), principal.role(), principal.organizationId(), "login", "/showcase", "accepted");
                response.sendRedirect("/showcase");
            } catch (HospitalRejection ex) {
                events.record("denied", "", "", "login", "/showcase", ex.code);
                response.sendRedirect("/ward/login?aviso=no-autorizado");
            }
        };
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

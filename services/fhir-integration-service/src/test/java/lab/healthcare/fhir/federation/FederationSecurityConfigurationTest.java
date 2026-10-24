package lab.healthcare.fhir.federation;

import lab.healthcare.fhir.federation.audit.FederationSecurityAudit;
import lab.healthcare.fhir.federation.audit.FederationSecurityAuditEvent;
import lab.healthcare.fhir.federation.audit.FederationSecurityAuditRecorder;
import lab.healthcare.fhir.federation.audit.FederationSecurityAuditUnavailable;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.boot.context.properties.bind.Bindable;
import org.springframework.boot.context.properties.bind.Binder;
import org.springframework.boot.env.YamlPropertySourceLoader;
import org.springframework.core.io.ClassPathResource;
import org.springframework.mock.web.MockFilterChain;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.mock.env.MockEnvironment;

import java.io.IOException;
import java.nio.file.Path;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class FederationSecurityConfigurationTest {

    @Test
    void environmentAuditPathOverridesTheLabDefaultAndCreatesItsParents(@TempDir Path temp)
            throws IOException {
        Path configured = temp.resolve("configured").resolve("security-audit.sqlite");
        MockEnvironment environment = new MockEnvironment()
                .withProperty("FEDERATION_SECURITY_AUDIT_STORE_PATH", configured.toString())
                .withProperty("java.io.tmpdir", temp.resolve("default").toString());
        new YamlPropertySourceLoader()
                .load("application", new ClassPathResource("application.yml"))
                .forEach(environment.getPropertySources()::addLast);
        FederationProperties properties = Binder.get(environment)
                .bind("federation", Bindable.of(FederationProperties.class))
                .orElseThrow(() -> new IllegalStateException("Federation properties did not bind"));

        FederationSecurityAuditRecorder recorder =
                new FederationConfiguration().federationSecurityAuditRecorder(properties);

        assertThat(recorder).isNotNull();
        assertThat(properties.getSecurityAudit().getStorePath()).isEqualTo(configured.toString());
        assertThat(configured).exists().isRegularFile();
        assertThat(temp.resolve("default").resolve("healthcare-lab-federation").resolve("security-audit.sqlite"))
                .doesNotExist();
    }

    @Test
    void labDefaultResolvesUnderTheJavaTemporaryDirectory(@TempDir Path temp) throws IOException {
        MockEnvironment environment = new MockEnvironment()
                .withProperty("java.io.tmpdir", temp.toString());
        new YamlPropertySourceLoader()
                .load("application", new ClassPathResource("application.yml"))
                .forEach(environment.getPropertySources()::addLast);
        FederationProperties properties = Binder.get(environment)
                .bind("federation", Bindable.of(FederationProperties.class))
                .orElseThrow(() -> new IllegalStateException("Federation properties did not bind"));
        Path expected = temp.resolve("healthcare-lab-federation").resolve("security-audit.sqlite");

        new FederationConfiguration().federationSecurityAuditRecorder(properties);

        assertThat(Path.of(properties.getSecurityAudit().getStorePath()).toAbsolutePath().normalize())
                .isEqualTo(expected.toAbsolutePath().normalize());
        assertThat(expected).exists().isRegularFile();
    }

    @Test
    void missingAndInvalidTokensProduceOneAnonymousDenialEach() throws Exception {
        List<FederationSecurityAuditEvent> events = new ArrayList<>();
        var filter = new FederationSecurityConfiguration.FederationParticipantFilter(
                Map.of("mini-his", "synthetic-participant-token"),
                audit(events));

        MockHttpServletResponse missing = invoke(filter, null);
        MockHttpServletResponse invalid = invoke(filter, "wrong-synthetic-token");

        assertThat(missing.getStatus()).isEqualTo(401);
        assertThat(invalid.getStatus()).isEqualTo(401);
        assertThat(events).extracting(FederationSecurityAuditEvent::reasonCode)
                .containsExactly("participant_token_missing", "participant_token_invalid");
        assertThat(events).allSatisfy(event -> {
            assertThat(event.actorType()).isEqualTo("anonymous");
            assertThat(event.actorId()).isEqualTo("anonymous");
            assertThat(event.organizationId()).isNull();
            assertThat(event.outcome()).isEqualTo("denied");
        });
        assertThat(events.toString())
                .doesNotContain("synthetic-participant-token")
                .doesNotContain("wrong-synthetic-token");
    }

    @Test
    void validTokenSetsOnlyTheServerResolvedCallerAndDefersAuditToAuthorization() throws Exception {
        List<FederationSecurityAuditEvent> events = new ArrayList<>();
        var filter = new FederationSecurityConfiguration.FederationParticipantFilter(
                Map.of("mini-his", "synthetic-participant-token"),
                audit(events));
        MockHttpServletRequest request = request();
        request.addHeader("X-Service-Token", "synthetic-participant-token");
        request.addHeader("X-Federation-Caller", "mini-lis");
        MockHttpServletResponse response = new MockHttpServletResponse();

        filter.doFilter(request, response, new MockFilterChain());

        assertThat(response.getStatus()).isEqualTo(200);
        assertThat(request.getAttribute(FederationSecurityConfiguration.CALLER_ATTRIBUTE))
                .isEqualTo("mini-his");
        assertThat(events).isEmpty();
    }

    @Test
    void whitespaceWrappedAndDuplicateTokensAreInvalid() throws Exception {
        List<FederationSecurityAuditEvent> events = new ArrayList<>();
        var filter = new FederationSecurityConfiguration.FederationParticipantFilter(
                Map.of("mini-his", "synthetic-participant-token"),
                audit(events));

        MockHttpServletResponse wrapped = invoke(filter, " synthetic-participant-token ");
        MockHttpServletResponse unicode = invoke(filter, "tökén-inválido");
        MockHttpServletRequest duplicateRequest = request();
        duplicateRequest.addHeader("X-Service-Token", "synthetic-participant-token");
        duplicateRequest.addHeader("X-Service-Token", "synthetic-participant-token");
        MockHttpServletResponse duplicate = new MockHttpServletResponse();
        filter.doFilter(duplicateRequest, duplicate, new MockFilterChain());

        assertThat(wrapped.getStatus()).isEqualTo(401);
        assertThat(unicode.getStatus()).isEqualTo(401);
        assertThat(duplicate.getStatus()).isEqualTo(401);
        assertThat(duplicateRequest.getAttribute(FederationSecurityConfiguration.CALLER_ATTRIBUTE)).isNull();
        assertThat(events).extracting(FederationSecurityAuditEvent::reasonCode)
                .containsExactly(
                        "participant_token_invalid",
                        "participant_token_invalid",
                        "participant_token_invalid");
    }

    @Test
    void auditFailureChangesAuthenticationRejectionToUnavailable() throws Exception {
        var filter = new FederationSecurityConfiguration.FederationParticipantFilter(
                Map.of("mini-his", "synthetic-participant-token"),
                new FederationSecurityAudit(event -> {
                    throw new FederationSecurityAuditUnavailable();
                }));

        MockHttpServletResponse response = invoke(filter, null);

        assertThat(response.getStatus()).isEqualTo(503);
        assertThat(response.getContentAsByteArray()).isEmpty();
    }

    private static MockHttpServletResponse invoke(
            FederationSecurityConfiguration.FederationParticipantFilter filter,
            String token) throws Exception {
        MockHttpServletRequest request = request();
        if (token != null) {
            request.addHeader("X-Service-Token", token);
        }
        MockHttpServletResponse response = new MockHttpServletResponse();
        filter.doFilter(request, response, new MockFilterChain());
        return response;
    }

    private static MockHttpServletRequest request() {
        MockHttpServletRequest request = new MockHttpServletRequest(
                "POST", "/api/clinical-federation/v1/context");
        request.setRequestURI("/api/clinical-federation/v1/context");
        return request;
    }

    private static FederationSecurityAudit audit(List<FederationSecurityAuditEvent> events) {
        return new FederationSecurityAudit(
                events::add,
                Clock.fixed(Instant.parse("2026-10-23T12:00:00Z"), ZoneOffset.UTC));
    }
}

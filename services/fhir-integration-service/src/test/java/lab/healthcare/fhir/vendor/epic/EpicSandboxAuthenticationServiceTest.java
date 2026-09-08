package lab.healthcare.fhir.vendor.epic;

import lab.healthcare.fhir.smart.SmartAuthorizationCoordinator;
import lab.healthcare.fhir.smart.SmartAuthorizationStart;
import lab.healthcare.fhir.smart.SmartConfiguration;
import lab.healthcare.fhir.smart.SmartConfigurationClient;

import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class EpicSandboxAuthenticationServiceTest {

    private final EpicProfileValidator validator = new EpicProfileValidator();
    private final SmartConfigurationClient smartConfigurationClient = mock(SmartConfigurationClient.class);
    private final SmartAuthorizationCoordinator coordinator = mock(SmartAuthorizationCoordinator.class);
    private final EpicSandboxAuthenticationService service =
            new EpicSandboxAuthenticationService(validator, smartConfigurationClient, coordinator);

    @Test
    void disabledProfileDoesNotStartAuthorization() {
        EpicIntegrationProfile profile = EpicIntegrationProfileTest.completePublicPkce();

        EpicSandboxAuthReadiness readiness = service.inspect(profile);

        assertThat(readiness.state()).isEqualTo(EpicSandboxAuthReadinessState.DISABLED);
        assertThat(readiness.toString()).doesNotContain("lab-epic-placeholder");
        assertThatThrownBy(() -> service.startAuthorization(profile))
                .isInstanceOf(EpicProfileException.class)
                .hasMessageContaining("disabled")
                .hasMessageNotContaining("access_token");
    }

    @Test
    void enabledSandboxStartsGenericPkceWithoutInventingHosts() {
        EpicIntegrationProfile profile = EpicIntegrationProfileTest.enabledCompletePublicPkce();
        SmartConfiguration discovered = new SmartConfiguration(
                "http://127.0.0.1/does-not-contact-epic/authorize",
                "http://127.0.0.1/does-not-contact-epic/token",
                List.of("patient/Patient.read"),
                List.of("code"),
                List.of("S256"),
                List.of());
        when(smartConfigurationClient.fetch(profile.smartConfigurationUrl())).thenReturn(discovered);
        when(coordinator.start(any(), eq(discovered), eq(EpicIntegrationProfile.SANDBOX_SERVER)))
                .thenReturn(new SmartAuthorizationStart(
                        EpicIntegrationProfile.SANDBOX_SERVER,
                        "http://127.0.0.1/does-not-contact-epic/authorize?code_challenge_method=S256",
                        "lab-state",
                        Instant.parse("2026-09-08T00:00:00Z")));

        EpicSandboxAuthReadiness readiness = service.inspect(profile);
        SmartAuthorizationStart start = service.startAuthorization(profile);

        assertThat(readiness.state()).isEqualTo(EpicSandboxAuthReadinessState.READY_FOR_AUTHORIZATION);
        assertThat(start.destination()).isEqualTo(EpicIntegrationProfile.SANDBOX_SERVER);
        assertThat(start.authorizationUrl()).contains("code_challenge_method=S256");
        assertThat(start.toString()).doesNotContain("lab-epic-placeholder");
        verify(smartConfigurationClient).fetch(profile.smartConfigurationUrl());
    }
}

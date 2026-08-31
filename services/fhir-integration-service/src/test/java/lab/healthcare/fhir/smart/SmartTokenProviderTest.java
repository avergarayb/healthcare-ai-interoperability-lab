package lab.healthcare.fhir.smart;

import lab.healthcare.fhir.auth.AccessToken;
import lab.healthcare.fhir.auth.FhirAuthenticationSettings;
import lab.healthcare.fhir.auth.FhirAuthenticationType;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class SmartTokenProviderTest {

    private static final FhirAuthenticationSettings AUTH = new FhirAuthenticationSettings(
            FhirAuthenticationType.SMART_AUTHORIZATION_CODE,
            null,
            "lab-smart-app",
            "",
            "http://localhost:8180/fhir/.well-known/smart-configuration",
            "http://127.0.0.1:8081/smart/callback",
            "patient/Patient.read",
            "http://localhost:8180/fhir");

    private static final SmartConfiguration CONFIG = new SmartConfiguration(
            "http://localhost:9090/authorize",
            "http://localhost:9090/oauth/token",
            List.of("patient/Patient.read"),
            List.of("code"),
            List.of("S256"),
            List.of());

    @Mock
    private SmartConfigurationClient configurationClient;

    @Mock
    private AuthorizationCodeClient authorizationCodeClient;

    @Test
    void reusesUsableAccessToken() {
        Clock clock = Clock.fixed(Instant.parse("2026-08-26T12:00:00Z"), ZoneOffset.UTC);
        when(configurationClient.fetch(AUTH.smartConfigurationUrl())).thenReturn(CONFIG);
        when(authorizationCodeClient.authorizeSynthetically(AUTH, CONFIG)).thenReturn(
                new AccessToken(
                        "smart-1",
                        Instant.parse("2026-08-26T13:00:00Z"),
                        "refresh-1",
                        "patient/Patient.read",
                        "patient-001"));
        SmartTokenProvider provider = new SmartTokenProvider(
                configurationClient, authorizationCodeClient, AUTH, clock);

        assertThat(provider.accessToken()).isEqualTo("smart-1");
        assertThat(provider.accessToken()).isEqualTo("smart-1");
        verify(authorizationCodeClient, times(1)).authorizeSynthetically(AUTH, CONFIG);
    }

    @Test
    void refreshesWhenCachedTokenExpires() {
        MutableClock clock = new MutableClock(Instant.parse("2026-08-26T12:00:00Z"));
        when(configurationClient.fetch(AUTH.smartConfigurationUrl())).thenReturn(CONFIG);
        when(authorizationCodeClient.authorizeSynthetically(AUTH, CONFIG)).thenReturn(
                new AccessToken(
                        "smart-1",
                        Instant.parse("2026-08-26T12:01:00Z"),
                        "refresh-1",
                        "patient/Patient.read",
                        "patient-001"));
        when(authorizationCodeClient.refreshAccessToken(AUTH, CONFIG.tokenEndpoint(), "refresh-1")).thenReturn(
                new AccessToken(
                        "smart-2",
                        Instant.parse("2026-08-26T13:01:00Z"),
                        "refresh-2",
                        "patient/Patient.read",
                        "patient-001"));
        SmartTokenProvider provider = new SmartTokenProvider(
                configurationClient, authorizationCodeClient, AUTH, clock);

        assertThat(provider.accessToken()).isEqualTo("smart-1");
        clock.set(Instant.parse("2026-08-26T12:00:45Z"));
        assertThat(provider.accessToken()).isEqualTo("smart-2");
        verify(authorizationCodeClient, times(1)).refreshAccessToken(AUTH, CONFIG.tokenEndpoint(), "refresh-1");
    }

    @Test
    void rejectsIncompatibleDiscoveredMetadataBeforeAuthorization() {
        SmartConfiguration incompatible = new SmartConfiguration(
                "http://localhost:9090/authorize",
                "http://localhost:9090/oauth/token",
                List.of(),
                List.of("code"),
                List.of("plain"),
                List.of());
        when(configurationClient.fetch(AUTH.smartConfigurationUrl())).thenReturn(incompatible);
        SmartTokenProvider provider = new SmartTokenProvider(
                configurationClient, authorizationCodeClient, AUTH, Clock.systemUTC());

        assertThatThrownBy(provider::accessToken)
                .isInstanceOf(SmartCompatibilityException.class)
                .hasMessageContaining("S256");
        verify(authorizationCodeClient, never()).authorizeSynthetically(AUTH, incompatible);
    }

    private static final class MutableClock extends Clock {

        private Instant instant;

        private MutableClock(Instant instant) {
            this.instant = instant;
        }

        void set(Instant instant) {
            this.instant = instant;
        }

        @Override
        public ZoneOffset getZone() {
            return ZoneOffset.UTC;
        }

        @Override
        public Clock withZone(java.time.ZoneId zone) {
            return this;
        }

        @Override
        public Instant instant() {
            return instant;
        }
    }
}

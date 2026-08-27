package lab.healthcare.fhir.client;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class CachingAccessTokenProviderTest {

    private static final FhirAuthenticationSettings AUTH = new FhirAuthenticationSettings(
            FhirAuthenticationType.OAUTH2_CLIENT_CREDENTIALS,
            "http://localhost:9090/oauth/token",
            "lab-client",
            "lab-secret");

    @Mock
    private OAuth2TokenClient tokenClient;

    @Test
    void reusesCachedTokenWhileUsable() {
        Clock clock = Clock.fixed(Instant.parse("2026-08-26T12:00:00Z"), ZoneOffset.UTC);
        when(tokenClient.fetchAccessToken(AUTH)).thenReturn(
                new AccessToken("lab-access-token", Instant.parse("2026-08-26T13:00:00Z")));
        CachingAccessTokenProvider provider = new CachingAccessTokenProvider(tokenClient, AUTH, clock);

        String first = provider.accessToken();
        String second = provider.accessToken();

        assertThat(first).isEqualTo("lab-access-token");
        assertThat(second).isEqualTo("lab-access-token");
        verify(tokenClient, times(1)).fetchAccessToken(AUTH);
    }

    @Test
    void fetchesNewTokenWhenCachedTokenExpires() {
        MutableClock clock = new MutableClock(Instant.parse("2026-08-26T12:00:00Z"));
        when(tokenClient.fetchAccessToken(AUTH))
                .thenReturn(new AccessToken("token-1", Instant.parse("2026-08-26T12:01:00Z")))
                .thenReturn(new AccessToken("token-2", Instant.parse("2026-08-26T13:01:00Z")));
        CachingAccessTokenProvider provider = new CachingAccessTokenProvider(tokenClient, AUTH, clock);

        String first = provider.accessToken();
        clock.set(Instant.parse("2026-08-26T12:00:45Z"));
        String second = provider.accessToken();

        assertThat(first).isEqualTo("token-1");
        assertThat(second).isEqualTo("token-2");
        verify(tokenClient, times(2)).fetchAccessToken(AUTH);
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

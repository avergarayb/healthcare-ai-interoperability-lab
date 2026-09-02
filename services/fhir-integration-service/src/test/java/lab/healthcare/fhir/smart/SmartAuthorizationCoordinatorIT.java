package lab.healthcare.fhir.smart;

import lab.healthcare.fhir.auth.AccessToken;
import lab.healthcare.fhir.auth.AccessTokenProvider;
import lab.healthcare.fhir.auth.FhirAuthenticationSettings;
import lab.healthcare.fhir.auth.IssuedAccessTokenProvider;
import lab.healthcare.fhir.server.FhirServerProfile;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest(
        webEnvironment = SpringBootTest.WebEnvironment.NONE,
        properties = {
                "fhir.active-server=smart-lab",
                "fhir.servers.smart-lab.enabled=true"
        })
class SmartAuthorizationCoordinatorIT {

    @Autowired
    private FhirServerProfile activeFhirServerProfile;

    @Autowired
    private SmartConfigurationClient smartConfigurationClient;

    @Autowired
    private SmartAuthorizationCoordinator smartAuthorizationCoordinator;

    private final HttpClient httpClient = HttpClient.newBuilder()
            .followRedirects(HttpClient.Redirect.NEVER)
            .build();

    @Test
    void interactiveCallbackExchangeIssuesAccessTokenProviderWithoutReadingPatient() throws Exception {
        FhirAuthenticationSettings authentication = activeFhirServerProfile.authentication();
        SmartConfiguration configuration = smartConfigurationClient.fetch(SmartDiscoveryUrl.from(authentication));

        SmartAuthorizationStart start =
                smartAuthorizationCoordinator.start(authentication, configuration, "smart-lab");
        HttpResponse<String> authorize = httpClient.send(
                HttpRequest.newBuilder(URI.create(start.authorizationUrl())).GET().build(),
                HttpResponse.BodyHandlers.ofString());
        String location = authorize.headers().firstValue("location").orElse("");
        AccessToken token = smartAuthorizationCoordinator.complete(location);
        AccessTokenProvider provider = new IssuedAccessTokenProvider(token);

        assertThat(authorize.statusCode()).isEqualTo(302);
        assertThat(start.authorizationUrl()).contains("code_challenge_method=S256");
        assertThat(start.authorizationUrl()).contains("aud=");
        assertThat(token.value()).startsWith("smart-");
        assertThat(provider.accessToken()).startsWith("smart-");
        assertThat(token.toString()).doesNotContain(token.value());
        assertThat(start.toString()).doesNotContain("code_verifier");
    }
}

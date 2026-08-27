package lab.healthcare.fhir.auth.oauth2;

import lab.healthcare.fhir.auth.AccessToken;
import lab.healthcare.fhir.auth.AccessTokenProvider;
import lab.healthcare.fhir.auth.FhirAuthenticationType;
import lab.healthcare.fhir.client.FhirService;
import lab.healthcare.fhir.client.SyntheticPatients;
import lab.healthcare.fhir.server.FhirServerProfile;

import ca.uhn.fhir.rest.client.api.IGenericClient;
import org.hl7.fhir.r4.model.Patient;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestInstance;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest(
        webEnvironment = SpringBootTest.WebEnvironment.NONE,
        properties = {
                "fhir.active-server=secured-lab",
                "fhir.servers.secured-lab.enabled=true",
                "fhir.servers.secured-lab.authentication.client-secret=lab-secret"
        })
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
class FhirOauth2AuthenticationIT {

    private static final String TOKEN_URL = "http://localhost:9090/oauth/token";
    private static final String PATIENT_URL = "http://localhost:8180/fhir/Patient/patient-001";

    @Autowired
    private FhirServerProfile activeFhirServerProfile;

    @Autowired
    private IGenericClient fhirClient;

    @Autowired
    private FhirService fhirService;

    @Autowired
    private OAuth2TokenClient oauth2TokenClient;

    @Autowired
    private AccessTokenProvider accessTokenProvider;

    private final HttpClient httpClient = HttpClient.newHttpClient();

    @BeforeAll
    void seedSyntheticPatientsThroughSecuredClient() {
        SyntheticPatients.seed(fhirClient);
    }

    @Test
    void clientCredentialsTokenEndpointIssuesBearerToken() {
        AccessToken token = oauth2TokenClient.fetchAccessToken(activeFhirServerProfile.authentication());

        assertThat(token.value()).isEqualTo("lab-access-token");
        assertThat(token.expiresAt()).isAfter(java.time.Instant.now().plusSeconds(3000));
    }

    @Test
    void gatewayRejectsMissingAndInvalidBearerTokens() throws Exception {
        HttpResponse<String> missing = httpClient.send(
                HttpRequest.newBuilder(URI.create(PATIENT_URL)).GET().build(),
                HttpResponse.BodyHandlers.ofString());
        HttpResponse<String> invalid = httpClient.send(
                HttpRequest.newBuilder(URI.create(PATIENT_URL))
                        .header("Authorization", "Bearer invalid-token")
                        .GET()
                        .build(),
                HttpResponse.BodyHandlers.ofString());

        assertThat(missing.statusCode()).isEqualTo(401);
        assertThat(invalid.statusCode()).isEqualTo(401);
        assertThat(missing.body()).contains("invalid_token");
        assertThat(invalid.body()).contains("invalid_token");
    }

    @Test
    void gatewayAllowsValidBearerToken() throws Exception {
        HttpResponse<String> response = httpClient.send(
                HttpRequest.newBuilder(URI.create(PATIENT_URL))
                        .header("Authorization", "Bearer lab-access-token")
                        .header("Accept", "application/fhir+json")
                        .GET()
                        .build(),
                HttpResponse.BodyHandlers.ofString());

        assertThat(response.statusCode()).isEqualTo(200);
        assertThat(response.body()).contains("\"resourceType\": \"Patient\"");
        assertThat(response.body()).contains("patient-001");
    }

    @Test
    void fhirServiceReadsPatientWithoutKnowingOauth() {
        assertThat(activeFhirServerProfile.name()).isEqualTo("secured-lab");
        assertThat(activeFhirServerProfile.baseUrl()).isEqualTo("http://localhost:8180/fhir");
        assertThat(activeFhirServerProfile.authentication().type())
                .isEqualTo(FhirAuthenticationType.OAUTH2_CLIENT_CREDENTIALS);
        assertThat(fhirClient.getServerBase()).isEqualTo("http://localhost:8180/fhir");
        assertThat(accessTokenProvider.accessToken()).isEqualTo("lab-access-token");

        Patient patient = fhirService.readPatient("patient-001");

        assertThat(patient.getIdElement().getIdPart()).isEqualTo("patient-001");
        assertThat(patient.getNameFirstRep().getFamily()).isEqualTo("Garcia");
    }

    @Test
    void tokenEndpointRejectsWrongSecret() throws Exception {
        HttpResponse<String> response = httpClient.send(
                HttpRequest.newBuilder(URI.create(TOKEN_URL))
                        .header("Content-Type", "application/x-www-form-urlencoded")
                        .POST(HttpRequest.BodyPublishers.ofString(
                                "grant_type=client_credentials&client_id=lab-client&client_secret=wrong",
                                StandardCharsets.UTF_8))
                        .build(),
                HttpResponse.BodyHandlers.ofString());

        assertThat(response.statusCode()).isEqualTo(401);
        assertThat(response.body()).contains("invalid_client");
    }
}

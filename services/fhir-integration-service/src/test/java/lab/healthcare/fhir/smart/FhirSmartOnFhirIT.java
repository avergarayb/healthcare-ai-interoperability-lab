package lab.healthcare.fhir.smart;

import lab.healthcare.fhir.auth.AccessToken;
import lab.healthcare.fhir.auth.AccessTokenProvider;
import lab.healthcare.fhir.auth.FhirAuthenticationSettings;
import lab.healthcare.fhir.auth.FhirAuthenticationType;
import lab.healthcare.fhir.client.FhirService;
import lab.healthcare.fhir.client.SyntheticClinicalResources;
import lab.healthcare.fhir.client.SyntheticPatients;
import lab.healthcare.fhir.server.FhirServerProfile;

import ca.uhn.fhir.context.FhirContext;
import ca.uhn.fhir.rest.client.api.IGenericClient;
import org.hl7.fhir.r4.model.Bundle;
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
                "fhir.active-server=smart-lab",
                "fhir.servers.smart-lab.enabled=true"
        })
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
class FhirSmartOnFhirIT {

    private static final String PATIENT_URL = "http://localhost:8180/fhir/Patient/patient-001";
    private static final String OBSERVATION_URL =
            "http://localhost:8180/fhir/Observation?patient=patient-001";
    private static final String TOKEN_URL = "http://localhost:9090/oauth/token";

    @Autowired
    private FhirServerProfile activeFhirServerProfile;

    @Autowired
    private FhirService fhirService;

    @Autowired
    private AccessTokenProvider accessTokenProvider;

    @Autowired
    private SmartConfigurationClient smartConfigurationClient;

    @Autowired
    private AuthorizationCodeClient authorizationCodeClient;

    private final HttpClient httpClient = HttpClient.newBuilder()
            .followRedirects(HttpClient.Redirect.NEVER)
            .build();

    @BeforeAll
    void seedThroughUnsecuredHapi() {
        IGenericClient open = FhirContext.forR4().newRestfulGenericClient("http://localhost:8080/fhir");
        SyntheticPatients.seed(open);
        SyntheticClinicalResources.seed(open);
    }

    @Test
    void smartDiscoveryExposesAuthorizationCodeAndPkce() {
        SmartConfiguration configuration = smartConfigurationClient.fetch(
                activeFhirServerProfile.authentication().smartConfigurationUrl());

        assertThat(configuration.authorizationEndpoint()).isEqualTo("http://localhost:9090/authorize");
        assertThat(configuration.tokenEndpoint()).isEqualTo("http://localhost:9090/oauth/token");
        assertThat(configuration.responseTypesSupported()).contains("code");
        assertThat(configuration.codeChallengeMethodsSupported()).contains("S256");
        assertThat(configuration.scopesSupported()).contains("patient/Patient.read", "patient/Observation.read");
        assertThat(configuration.capabilities()).contains("launch-standalone", "client-public");
    }

    @Test
    void authorizationCodePkceExchangeReturnsPatientContext() throws Exception {
        FhirAuthenticationSettings authentication = activeFhirServerProfile.authentication();
        SmartConfiguration configuration = smartConfigurationClient.fetch(authentication.smartConfigurationUrl());
        AuthorizationSession session = authorizationCodeClient.createAuthorization(authentication, configuration);

        HttpResponse<String> authorize = httpClient.send(
                HttpRequest.newBuilder(URI.create(session.authorizationUrl())).GET().build(),
                HttpResponse.BodyHandlers.ofString());
        String location = authorize.headers().firstValue("location").orElse("");
        String code = authorizationCodeClient.authorizationCodeFromRedirect(location, session.state());
        AccessToken token = authorizationCodeClient.exchangeAuthorizationCode(
                authentication, configuration.tokenEndpoint(), code, session.codeVerifier());

        assertThat(authorize.statusCode()).isEqualTo(302);
        assertThat(token.value()).startsWith("smart-");
        assertThat(token.refreshToken()).startsWith("refresh-");
        assertThat(token.scope()).contains("patient/Patient.read");
        assertThat(token.patient()).isEqualTo("patient-001");
    }

    @Test
    void fhirServiceReadsPatientWithoutKnowingSmart() {
        assertThat(activeFhirServerProfile.name()).isEqualTo("smart-lab");
        assertThat(activeFhirServerProfile.authentication().type())
                .isEqualTo(FhirAuthenticationType.SMART_AUTHORIZATION_CODE);
        assertThat(accessTokenProvider.accessToken()).startsWith("smart-");

        Patient patient = fhirService.readPatient("patient-001");
        Bundle observations = fhirService.searchObservationsByPatient("patient-001");

        assertThat(patient.getIdElement().getIdPart()).isEqualTo("patient-001");
        assertThat(fhirService.extractObservations(observations))
                .extracting(observation -> observation.getIdElement().getIdPart())
                .contains("obs-001");
    }

    @Test
    void gatewayRejectsMissingTokenAndInsufficientScope() throws Exception {
        HttpResponse<String> missing = get(PATIENT_URL, null);
        AccessToken patientOnly = authorizeWithScope("patient/Patient.read");
        HttpResponse<String> forbidden = get(OBSERVATION_URL, patientOnly.value());
        AccessToken patientAndObservation = authorizeWithScope(
                "patient/Patient.read patient/Observation.read");
        HttpResponse<String> allowed = get(OBSERVATION_URL, patientAndObservation.value());

        assertThat(missing.statusCode()).isEqualTo(401);
        assertThat(forbidden.statusCode()).isEqualTo(403);
        assertThat(forbidden.body()).contains("insufficient_scope");
        assertThat(allowed.statusCode()).isEqualTo(200);
        assertThat(allowed.body()).contains("obs-001");
    }

    @Test
    void refreshTokenIssuesNewAccessTokenForFhir() throws Exception {
        AccessToken original = authorizeWithScope("patient/Patient.read patient/Observation.read");
        HttpResponse<String> refreshed = httpClient.send(
                HttpRequest.newBuilder(URI.create(TOKEN_URL))
                        .header("Content-Type", "application/x-www-form-urlencoded")
                        .POST(HttpRequest.BodyPublishers.ofString(
                                "grant_type=refresh_token&refresh_token="
                                        + original.refreshToken()
                                        + "&client_id=lab-smart-app",
                                StandardCharsets.UTF_8))
                        .build(),
                HttpResponse.BodyHandlers.ofString());
        AccessToken next = authorizationCodeClient.parseTokenResponse(
                refreshed.statusCode(), refreshed.body());
        HttpResponse<String> fhir = get(PATIENT_URL, next.value());

        assertThat(refreshed.statusCode()).isEqualTo(200);
        assertThat(next.value()).isNotEqualTo(original.value());
        assertThat(next.patient()).isEqualTo("patient-001");
        assertThat(fhir.statusCode()).isEqualTo(200);
        assertThat(fhir.body()).contains("patient-001");
    }

    private AccessToken authorizeWithScope(String scope) {
        FhirAuthenticationSettings authentication = new FhirAuthenticationSettings(
                FhirAuthenticationType.SMART_AUTHORIZATION_CODE,
                null,
                "lab-smart-app",
                "",
                activeFhirServerProfile.authentication().smartConfigurationUrl(),
                "http://127.0.0.1:8081/smart/callback",
                scope,
                "http://localhost:8180/fhir");
        SmartConfiguration configuration = smartConfigurationClient.fetch(authentication.smartConfigurationUrl());
        return authorizationCodeClient.authorizeSynthetically(authentication, configuration);
    }

    private HttpResponse<String> get(String url, String accessToken) throws Exception {
        HttpRequest.Builder builder = HttpRequest.newBuilder(URI.create(url))
                .header("Accept", "application/fhir+json")
                .GET();
        if (accessToken != null) {
            builder.header("Authorization", "Bearer " + accessToken);
        }
        return httpClient.send(builder.build(), HttpResponse.BodyHandlers.ofString());
    }
}

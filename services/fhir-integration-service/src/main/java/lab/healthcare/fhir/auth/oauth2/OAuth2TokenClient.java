package lab.healthcare.fhir.auth.oauth2;

import lab.healthcare.fhir.auth.AccessToken;
import lab.healthcare.fhir.auth.FhirAuthenticationSettings;

import com.fasterxml.jackson.databind.ObjectMapper;

import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Clock;
import java.time.Duration;

public class OAuth2TokenClient {

    private final HttpClient httpClient;
    private final OAuth2TokenResponseParser parser;

    public OAuth2TokenClient() {
        this(HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(5)).build(), Clock.systemUTC());
    }

    OAuth2TokenClient(HttpClient httpClient, Clock clock) {
        this.httpClient = httpClient;
        this.parser = new OAuth2TokenResponseParser(new ObjectMapper(), clock);
    }

    public AccessToken fetchAccessToken(FhirAuthenticationSettings authentication) {
        if (authentication == null || !authentication.isClientCredentials()) {
            throw new IllegalArgumentException("OAuth2 client credentials settings must be provided");
        }
        String form = "grant_type=" + encode("client_credentials")
                + "&client_id=" + encode(authentication.clientId())
                + "&client_secret=" + encode(authentication.clientSecret());
        HttpRequest request = HttpRequest.newBuilder(URI.create(authentication.tokenUrl()))
                .timeout(Duration.ofSeconds(10))
                .header("Accept", "application/json")
                .header("Content-Type", "application/x-www-form-urlencoded")
                .POST(HttpRequest.BodyPublishers.ofString(form))
                .build();
        try {
            HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
            return parser.parse(response.statusCode(), response.body());
        } catch (OAuth2TokenException ex) {
            throw ex;
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
            throw new OAuth2TokenException("OAuth token endpoint unavailable", ex);
        } catch (Exception ex) {
            throw new OAuth2TokenException("OAuth token endpoint unavailable", ex);
        }
    }

    AccessToken parseResponse(int statusCode, String body) {
        return parser.parse(statusCode, body);
    }

    private static String encode(String value) {
        return URLEncoder.encode(value == null ? "" : value, StandardCharsets.UTF_8);
    }
}

package lab.healthcare.fhir.smart;

import lab.healthcare.fhir.auth.oauth2.OAuth2TokenException;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;

public class SmartConfigurationClient {

    private final HttpClient httpClient;
    private final ObjectMapper objectMapper;

    public SmartConfigurationClient() {
        this(HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(5)).build());
    }

    SmartConfigurationClient(HttpClient httpClient) {
        this.httpClient = httpClient;
        this.objectMapper = new ObjectMapper();
    }

    public SmartConfiguration fetch(String smartConfigurationUrl) {
        if (smartConfigurationUrl == null || smartConfigurationUrl.isBlank()) {
            throw new IllegalArgumentException("SMART configuration URL must be provided");
        }
        HttpRequest request = HttpRequest.newBuilder(URI.create(smartConfigurationUrl.trim()))
                .timeout(Duration.ofSeconds(10))
                .header("Accept", "application/json")
                .GET()
                .build();
        try {
            HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
            return parse(response.statusCode(), response.body());
        } catch (OAuth2TokenException ex) {
            throw ex;
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
            throw new OAuth2TokenException("SMART discovery endpoint unavailable", ex);
        } catch (Exception ex) {
            throw new OAuth2TokenException("SMART discovery endpoint unavailable", ex);
        }
    }

    SmartConfiguration parse(int statusCode, String body) {
        if (statusCode < 200 || statusCode >= 300) {
            throw new OAuth2TokenException("SMART discovery failed: HTTP " + statusCode);
        }
        JsonNode json = readJson(body);
        String authorizationEndpoint = text(json, "authorization_endpoint");
        String tokenEndpoint = text(json, "token_endpoint");
        if (authorizationEndpoint == null || authorizationEndpoint.isBlank()) {
            throw new OAuth2TokenException("SMART discovery failed: authorization_endpoint missing");
        }
        if (tokenEndpoint == null || tokenEndpoint.isBlank()) {
            throw new OAuth2TokenException("SMART discovery failed: token_endpoint missing");
        }
        return new SmartConfiguration(
                authorizationEndpoint,
                tokenEndpoint,
                strings(json, "scopes_supported"),
                strings(json, "response_types_supported"),
                strings(json, "code_challenge_methods_supported"),
                strings(json, "capabilities"));
    }

    private JsonNode readJson(String body) {
        if (body == null || body.isBlank()) {
            throw new OAuth2TokenException("SMART discovery failed: empty response");
        }
        try {
            return objectMapper.readTree(body);
        } catch (Exception ex) {
            throw new OAuth2TokenException("SMART discovery failed: response is not JSON", ex);
        }
    }

    private static String text(JsonNode json, String field) {
        if (json == null || !json.hasNonNull(field)) {
            return null;
        }
        return json.get(field).asText();
    }

    private static List<String> strings(JsonNode json, String field) {
        List<String> values = new ArrayList<>();
        if (json == null || !json.has(field) || !json.get(field).isArray()) {
            return List.copyOf(values);
        }
        for (JsonNode node : json.get(field)) {
            if (node != null && !node.isNull()) {
                values.add(node.asText());
            }
        }
        return List.copyOf(values);
    }
}

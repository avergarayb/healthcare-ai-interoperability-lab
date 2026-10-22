package lab.healthcare.fhir.exchange;

import lab.healthcare.fhir.clinicalread.minilis.MiniLisFhirMapping;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;

import java.io.IOException;
import java.net.InetAddress;
import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;

/**
 * HTTP connector for Mini LIS. It speaks the proprietary REST contract and
 * does not open the laboratory database.
 */
public final class MiniLisExchangeConnector implements OrderDestination, ResultSource {

    static final String TOKEN_HEADER = "X-Service-Token";

    private final String baseUrl;
    private final String serviceToken;
    private final Duration readTimeout;
    private final HttpClient http;
    private final ObjectMapper json;
    private final MiniLisFhirMapping mapping;

    public MiniLisExchangeConnector(
            String baseUrl,
            String serviceToken,
            Duration connectTimeout,
            Duration readTimeout,
            ObjectMapper json) {
        if (json == null) {
            throw new IllegalArgumentException("JSON mapper must be provided");
        }
        String normalized = baseUrl == null ? "" : baseUrl.trim().replaceAll("/+$", "");
        if (!loopbackHttp(normalized)) {
            throw new IllegalArgumentException("Mini LIS exchange URL must be an HTTP loopback address");
        }
        this.baseUrl = normalized;
        this.serviceToken = serviceToken == null ? "" : serviceToken;
        this.readTimeout = bounded(readTimeout);
        this.http = HttpClient.newBuilder()
                .connectTimeout(bounded(connectTimeout))
                .followRedirects(HttpClient.Redirect.NEVER)
                .build();
        this.json = json;
        this.mapping = new MiniLisFhirMapping(json);
    }

    @Override
    public String systemKey() {
        return "mini-lis";
    }

    @Override
    public String resolvePatient(String requestingOrganizationId, PatientIdentity identity) {
        String query = "/patients?organizationId=" + encode(requestingOrganizationId)
                + "&externalId=" + encode(identity.identifierValue());
        HttpResult found = send("GET", query, null);
        if (found.status() == 200 && found.body().isArray() && !found.body().isEmpty()) {
            return found.body().get(0).path("patientId").asText();
        }
        ObjectNode body = json.createObjectNode();
        body.put("organizationId", requestingOrganizationId);
        body.put("externalId", identity.identifierValue());
        body.put("familyName", identity.familyName());
        body.put("givenName", identity.givenName());
        body.put("birthDate", identity.birthDate().toString());
        body.put("administrativeSex", identity.administrativeSex());
        HttpResult created = send("POST", "/patients", body);
        if (created.status() == 201) {
            return created.body().path("patientId").asText();
        }
        if (created.status() == 409) {
            HttpResult again = send("GET", query, null);
            if (again.status() == 200 && again.body().isArray() && !again.body().isEmpty()) {
                return again.body().get(0).path("patientId").asText();
            }
        }
        throw ExchangeException.unavailable();
    }

    @Override
    public AcceptedOrder accept(DestinationCommand command) {
        ObjectNode body = json.createObjectNode();
        body.put("patientId", command.patientId());
        body.put("requestingOrganizationId", command.requestingOrganizationId());
        body.put("externalRequestId", command.externalRequestId());
        body.put("testCode", command.testCode());
        body.put("testDescription", command.testDescription());
        body.put("requestedAt", command.requestedAt().toString());
        HttpResult created = send("POST", "/orders", body);
        if (created.status() == 201) {
            return new AcceptedOrder(created.body().path("orderId").asText(), false);
        }
        if (created.status() == 409 && "duplicate".equals(created.body().path("error").asText())) {
            HttpResult existing = send(
                    "GET",
                    "/orders?requestingOrganizationId=" + encode(command.requestingOrganizationId())
                            + "&externalRequestId=" + encode(command.externalRequestId()),
                    null);
            if (existing.status() == 200) {
                return new AcceptedOrder(existing.body().path("orderId").asText(), true);
            }
        }
        if (created.status() == 400 || created.status() == 404) {
            throw ExchangeException.rejected();
        }
        throw ExchangeException.unavailable();
    }

    @Override
    public DestinationReport read(String destinationOrderId) {
        HttpResult order = send("GET", "/orders/" + encode(destinationOrderId), null);
        if (order.status() == 404) {
            throw ExchangeException.unavailable();
        }
        if (order.status() != 200) {
            throw ExchangeException.unavailable();
        }
        HttpResult results = send("GET", "/orders/" + encode(destinationOrderId) + "/results", null);
        if (results.status() != 200 || !results.body().isArray()) {
            throw ExchangeException.unavailable();
        }
        List<JsonNode> observations = new ArrayList<>();
        for (JsonNode result : results.body()) {
            observations.add(mapping.observation(result));
        }
        return new DestinationReport(
                mapping.serviceRequest(order.body()),
                mapping.diagnosticReport(order.body(), results.body()),
                observations);
    }

    private HttpResult send(String method, String path, JsonNode body) {
        if (serviceToken.isBlank()) {
            throw ExchangeException.unavailable();
        }
        HttpRequest.Builder request = HttpRequest.newBuilder(URI.create(baseUrl + path))
                .timeout(readTimeout)
                .header("Accept", "application/json")
                .header(TOKEN_HEADER, serviceToken);
        if ("POST".equals(method)) {
            request.header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString(body.toString(), StandardCharsets.UTF_8));
        } else {
            request.GET();
        }
        try {
            HttpResponse<String> response = http.send(request.build(), HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
            JsonNode parsed = response.body() == null || response.body().isBlank()
                    ? json.createObjectNode()
                    : json.readTree(response.body());
            return new HttpResult(response.statusCode(), parsed);
        } catch (IOException | InterruptedException | IllegalArgumentException ex) {
            if (ex instanceof InterruptedException) {
                Thread.currentThread().interrupt();
            }
            throw ExchangeException.unavailable();
        }
    }

    private static String encode(String value) {
        return URLEncoder.encode(value, StandardCharsets.UTF_8).replace("+", "%20");
    }

    private static boolean loopbackHttp(String baseUrl) {
        try {
            URI uri = URI.create(baseUrl);
            if (!"http".equalsIgnoreCase(uri.getScheme()) || uri.getHost() == null) {
                return false;
            }
            if ("localhost".equalsIgnoreCase(uri.getHost())) {
                return true;
            }
            return InetAddress.getByName(uri.getHost()).isLoopbackAddress();
        } catch (Exception ex) {
            return false;
        }
    }

    private static Duration bounded(Duration value) {
        if (value == null || value.isZero() || value.isNegative() || value.compareTo(Duration.ofSeconds(30)) > 0) {
            throw new IllegalArgumentException("Exchange timeout must be from 1ms through 30s");
        }
        return value;
    }

    private record HttpResult(int status, JsonNode body) {
    }
}

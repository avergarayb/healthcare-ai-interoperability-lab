package lab.healthcare.fhir.clinicalread.minilis;

import lab.healthcare.fhir.clinicalread.ClinicalReadException;
import lab.healthcare.fhir.clinicalread.ClinicalReadLimits;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.io.IOException;
import java.net.InetAddress;
import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;

/**
 * Read-only HTTP client for the Mini LIS proprietary API. It does not open the
 * laboratory database and it does not call HAPI.
 */
final class MiniLisClient {

    static final String TOKEN_HEADER = "X-Service-Token";

    private final String baseUrl;
    private final String serviceToken;
    private final Duration readTimeout;
    private final HttpClient http;
    private final ObjectMapper json;

    MiniLisClient(String baseUrl, String serviceToken, Duration connectTimeout, Duration readTimeout, ObjectMapper json) {
        if (json == null) {
            throw new IllegalArgumentException("JSON mapper must be provided");
        }
        String normalized = baseUrl == null ? "" : baseUrl.trim().replaceAll("/+$", "");
        if (!loopbackHttp(normalized)) {
            throw new IllegalArgumentException("Mini LIS base URL must be an HTTP loopback address");
        }
        if (serviceToken == null || serviceToken.isBlank()) {
            throw new IllegalArgumentException("Mini LIS service token must be provided");
        }
        this.baseUrl = normalized;
        this.serviceToken = serviceToken;
        this.readTimeout = bounded(readTimeout, "read");
        this.http = HttpClient.newBuilder()
                .connectTimeout(bounded(connectTimeout, "connect"))
                .followRedirects(HttpClient.Redirect.NEVER)
                .build();
        this.json = json;
    }

    MiniLisResponse getOne(String path) {
        return exchange(path, false);
    }

    MiniLisResponse getList(String path) {
        String separator = path.contains("?") ? "&" : "?";
        return exchange(path + separator + "limit=" + ClinicalReadLimits.MAX_RESOURCES, true);
    }

    private MiniLisResponse exchange(String path, boolean list) {
        HttpRequest request = HttpRequest.newBuilder(URI.create(baseUrl + path))
                .timeout(readTimeout)
                .header("Accept", "application/json")
                .header(TOKEN_HEADER, serviceToken)
                .GET()
                .build();
        HttpResponse<String> response;
        try {
            response = http.send(request, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
        } catch (IOException | InterruptedException | IllegalArgumentException ex) {
            if (ex instanceof InterruptedException) {
                Thread.currentThread().interrupt();
            }
            throw ClinicalReadException.unavailable();
        }
        if (response.statusCode() == 404) {
            return new MiniLisResponse(404, parse(response.body()), false);
        }
        if (response.statusCode() != 200) {
            throw ClinicalReadException.unavailable();
        }
        JsonNode body = parse(response.body());
        boolean truncated = list && truncated(response, body);
        return new MiniLisResponse(200, body, truncated);
    }

    private JsonNode parse(String body) {
        if (body == null || body.isBlank()) {
            throw ClinicalReadException.unavailable();
        }
        try {
            JsonNode parsed = json.readTree(body);
            if (parsed == null || parsed.isNull()) {
                throw ClinicalReadException.unavailable();
            }
            return parsed;
        } catch (IOException ex) {
            throw ClinicalReadException.unavailable();
        }
    }

    private static boolean truncated(HttpResponse<String> response, JsonNode body) {
        String more = response.headers().firstValue("X-More-Results").orElse("");
        if ("true".equals(more)) {
            return true;
        }
        if ("false".equals(more)) {
            return false;
        }
        return body.isArray() && body.size() >= ClinicalReadLimits.MAX_RESOURCES;
    }

    static String encode(String value) {
        return URLEncoder.encode(value, StandardCharsets.UTF_8).replace("+", "%20");
    }

    private static boolean loopbackHttp(String baseUrl) {
        try {
            URI uri = URI.create(baseUrl);
            if (!"http".equalsIgnoreCase(uri.getScheme()) || uri.getHost() == null) {
                return false;
            }
            String host = uri.getHost();
            if ("localhost".equalsIgnoreCase(host)) {
                return true;
            }
            return InetAddress.getByName(host).isLoopbackAddress();
        } catch (Exception ex) {
            return false;
        }
    }

    private static Duration bounded(Duration value, String name) {
        if (value == null || value.isZero() || value.isNegative() || value.compareTo(Duration.ofSeconds(30)) > 0) {
            throw new IllegalArgumentException("Mini LIS " + name + " timeout must be from 1ms through 30s");
        }
        return value;
    }

    record MiniLisResponse(int status, JsonNode body, boolean truncated) {
    }
}

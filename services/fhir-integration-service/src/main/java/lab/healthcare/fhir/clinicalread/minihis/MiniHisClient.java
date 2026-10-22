package lab.healthcare.fhir.clinicalread.minihis;

import lab.healthcare.fhir.clinicalread.ClinicalReadException;
import lab.healthcare.fhir.clinicalread.ClinicalReadLimits;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.io.IOException;
import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;

/**
 * Read-only HTTP client for the Mini HIS proprietary API. It does not open the
 * simulator database and it does not call HAPI.
 */
final class MiniHisClient {

    private final String baseUrl;
    private final Duration readTimeout;
    private final HttpClient http;
    private final ObjectMapper json;

    MiniHisClient(String baseUrl, Duration connectTimeout, Duration readTimeout, ObjectMapper json) {
        if (json == null) {
            throw new IllegalArgumentException("JSON mapper must be provided");
        }
        String normalized = baseUrl == null ? "" : baseUrl.trim().replaceAll("/+$", "");
        if (normalized.isEmpty()) {
            throw new IllegalArgumentException("Mini HIS base URL must be provided");
        }
        this.baseUrl = normalized;
        this.readTimeout = bounded(readTimeout, "read");
        this.http = HttpClient.newBuilder()
                .connectTimeout(bounded(connectTimeout, "connect"))
                .followRedirects(HttpClient.Redirect.NEVER)
                .build();
        this.json = json;
    }

    MiniHisResponse getOne(String path) {
        return exchange(path, false);
    }

    MiniHisResponse getList(String path) {
        String separator = path.contains("?") ? "&" : "?";
        return exchange(path + separator + "limit=" + ClinicalReadLimits.MAX_RESOURCES, true);
    }

    private MiniHisResponse exchange(String path, boolean list) {
        HttpRequest request = HttpRequest.newBuilder(URI.create(baseUrl + path))
                .timeout(readTimeout)
                .header("Accept", "application/json")
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
            return new MiniHisResponse(404, parse(response.body()), false);
        }
        if (response.statusCode() != 200) {
            throw ClinicalReadException.unavailable();
        }
        JsonNode body = parse(response.body());
        boolean truncated = list && truncated(response, body);
        return new MiniHisResponse(200, body, truncated);
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

    private static Duration bounded(Duration value, String name) {
        if (value == null || value.isZero() || value.isNegative() || value.compareTo(Duration.ofSeconds(30)) > 0) {
            throw new IllegalArgumentException("Mini HIS " + name + " timeout must be from 1ms through 30s");
        }
        return value;
    }

    record MiniHisResponse(int status, JsonNode body, boolean truncated) {
    }
}

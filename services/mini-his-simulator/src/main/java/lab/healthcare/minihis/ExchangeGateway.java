package lab.healthcare.minihis;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

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
 * Calls FHIR Integration Service. This client has no Mini LIS address.
 */
@Component
public class ExchangeGateway {

    private static final Logger log = LoggerFactory.getLogger(ExchangeGateway.class);

    private final MiniHisSettings settings;
    private final ObjectMapper json;
    private final HttpClient http;

    public ExchangeGateway(MiniHisSettings settings, ObjectMapper json) {
        this.settings = settings;
        this.json = json;
        Duration connect = settings.getExchange().getConnectTimeout();
        this.http = HttpClient.newBuilder()
                .connectTimeout(connect == null ? Duration.ofSeconds(2) : connect)
                .followRedirects(HttpClient.Redirect.NEVER)
                .build();
    }

    public boolean configured() {
        String baseUrl = settings.getExchange().getBaseUrl();
        return baseUrl != null && !baseUrl.isBlank() && loopbackHttp(baseUrl.trim())
                && settings.getExchange().getServiceToken() != null
                && !settings.getExchange().getServiceToken().isBlank();
    }

    public JsonNode submit(ObjectNode order) {
        return send("POST", "/api/exchange/v1/orders", order);
    }

    public JsonNode report(String orderId) {
        return send("GET", "/api/exchange/v1/orders/" + encode(orderId) + "/report", null);
    }

    private JsonNode send(String method, String path, JsonNode body) {
        if (!configured()) {
            throw new ExchangeGatewayException(503, "exchange_unconfigured");
        }
        String baseUrl = settings.getExchange().getBaseUrl().trim().replaceAll("/+$", "");
        Duration read = settings.getExchange().getReadTimeout();
        HttpRequest.Builder request = HttpRequest.newBuilder(URI.create(baseUrl + path))
                .timeout(read == null ? Duration.ofSeconds(5) : read)
                .header("Accept", "application/json")
                .header("X-Service-Token", settings.getExchange().getServiceToken());
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
            if (response.statusCode() >= 400) {
                String code = parsed.path("error").asText("destination_unavailable");
                log.info("mini_his_exchange_failed status={} error={}", response.statusCode(), code);
                throw new ExchangeGatewayException(response.statusCode(), code);
            }
            return parsed;
        } catch (IOException | InterruptedException | IllegalArgumentException ex) {
            if (ex instanceof InterruptedException) {
                Thread.currentThread().interrupt();
            }
            log.info("mini_his_exchange_failed error=destination_unavailable");
            throw new ExchangeGatewayException(503, "destination_unavailable");
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

    public static final class ExchangeGatewayException extends RuntimeException {
        private final int status;
        private final String code;

        ExchangeGatewayException(int status, String code) {
            super(code);
            this.status = status;
            this.code = code;
        }

        public int status() {
            return status;
        }

        public String code() {
            return code;
        }
    }
}

package lab.healthcare.minihis;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.Map;

@Component
public class CriticalLabClient {

    private final String baseUrl;
    private final String serviceToken;
    private final ObjectMapper mapper = new ObjectMapper();
    private final HttpClient client = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(2)).build();

    public CriticalLabClient(
            @Value("${mini-his.inpatient.coordinator-url:}") String baseUrl,
            @Value("${MODEL_BOUNDARY_SERVICE_TOKEN:}") String serviceToken) {
        String trimmed = baseUrl == null ? "" : baseUrl.trim();
        this.baseUrl = trimmed.endsWith("/") ? trimmed.substring(0, trimmed.length() - 1) : trimmed;
        this.serviceToken = serviceToken == null ? "" : serviceToken.trim();
    }

    public Map<String, Object> prepare(Map<String, Object> body) {
        return post("/internal/critical-lab/prepare", body);
    }

    public Map<String, Object> decide(Map<String, Object> body) {
        return post("/internal/critical-lab/decisions", body);
    }

    public Map<String, Object> apply(Map<String, Object> body) {
        return post("/internal/critical-lab/apply", body);
    }

    private Map<String, Object> post(String path, Map<String, Object> body) {
        try {
            HttpRequest request = base(path)
                    .POST(HttpRequest.BodyPublishers.ofString(mapper.writeValueAsString(body)))
                    .header("Content-Type", "application/json")
                    .build();
            return read(client.send(request, HttpResponse.BodyHandlers.ofString()));
        } catch (InpatientRejection ex) {
            throw ex;
        } catch (Exception ex) {
            throw new InpatientRejection("critical_agent_unavailable", 503);
        }
    }

    private HttpRequest.Builder base(String path) {
        if (!baseUrl.startsWith("http://127.0.0.1:") || serviceToken.isBlank()) {
            throw new InpatientRejection("critical_agent_unconfigured", 503);
        }
        return HttpRequest.newBuilder(URI.create(baseUrl + path))
                .timeout(Duration.ofSeconds(5))
                .header("X-Service-Token", serviceToken)
                .header("Accept", "application/json");
    }

    private Map<String, Object> read(HttpResponse<String> response) throws Exception {
        if (response.statusCode() >= 400) {
            throw new InpatientRejection("critical_agent_rejected", response.statusCode());
        }
        return mapper.readValue(response.body(), new TypeReference<>() {});
    }
}

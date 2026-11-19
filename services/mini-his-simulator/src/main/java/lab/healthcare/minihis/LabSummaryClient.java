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
public class LabSummaryClient {

    private final String baseUrl;
    private final String serviceToken;
    private final ObjectMapper mapper = new ObjectMapper();
    private final HttpClient client = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(2)).build();

    public LabSummaryClient(
            @Value("${mini-his.inpatient.coordinator-url:}") String baseUrl,
            @Value("${MODEL_BOUNDARY_SERVICE_TOKEN:}") String serviceToken) {
        String trimmed = baseUrl == null ? "" : baseUrl.trim();
        this.baseUrl = trimmed.endsWith("/") ? trimmed.substring(0, trimmed.length() - 1) : trimmed;
        this.serviceToken = serviceToken == null ? "" : serviceToken.trim();
    }

    public Map<String, Object> latest() {
        try {
            return get("/internal/lab-summary/cases/latest", Duration.ofSeconds(2));
        } catch (RuntimeException ex) {
            return Map.of();
        }
    }

    public Map<String, Object> read(String caseId) {
        return get("/internal/lab-summary/cases/" + caseId(caseId), Duration.ofSeconds(10));
    }

    public Map<String, Object> prepare(String actorId) {
        return prepare(actorId, "");
    }

    public Map<String, Object> prepare(String actorId, String identityToken) {
        return post("/internal/lab-summary/cases", Map.of(
                "role", "clinician",
                "organizationId", "org-mini-his",
                "actorId", actorId), Duration.ofSeconds(40), identityToken);
    }

    public Map<String, Object> decide(String caseId, String decision, String actorId) {
        return decide(caseId, decision, actorId, "");
    }

    public Map<String, Object> decide(String caseId, String decision, String actorId, String identityToken) {
        return post("/internal/lab-summary/cases/" + caseId(caseId) + "/decision", Map.of(
                "role", "clinician",
                "organizationId", "org-mini-his",
                "actorId", actorId,
                "decision", decision), Duration.ofSeconds(10), identityToken);
    }

    public Map<String, Object> replay(String caseId, String actorId) {
        return replay(caseId, actorId, "");
    }

    public Map<String, Object> replay(String caseId, String actorId, String identityToken) {
        return post("/internal/lab-summary/cases/" + caseId(caseId) + "/replay", Map.of(
                "role", "clinician",
                "organizationId", "org-mini-his",
                "actorId", actorId), Duration.ofSeconds(40), identityToken);
    }

    private Map<String, Object> get(String path, Duration timeout) {
        try {
            HttpRequest request = base(path, timeout).GET().build();
            return read(client.send(request, HttpResponse.BodyHandlers.ofString()));
        } catch (InpatientRejection ex) {
            throw ex;
        } catch (Exception ex) {
            throw new InpatientRejection("summary_unavailable", 503);
        }
    }

    private Map<String, Object> post(String path, Map<String, Object> body, Duration timeout) {
        return post(path, body, timeout, "");
    }

    private Map<String, Object> post(String path, Map<String, Object> body, Duration timeout, String identityToken) {
        try {
            HttpRequest.Builder builder = base(path, timeout)
                    .POST(HttpRequest.BodyPublishers.ofString(mapper.writeValueAsString(body)))
                    .header("Content-Type", "application/json");
            if (identityToken != null && identityToken.chars().filter(ch -> ch == '.').count() == 2) {
                builder.header("Authorization", "Bearer " + identityToken);
            }
            HttpRequest request = builder.build();
            return read(client.send(request, HttpResponse.BodyHandlers.ofString()));
        } catch (InpatientRejection ex) {
            throw ex;
        } catch (Exception ex) {
            throw new InpatientRejection("summary_unavailable", 503);
        }
    }

    private HttpRequest.Builder base(String path, Duration timeout) {
        if (!baseUrl.startsWith("http://127.0.0.1:") || serviceToken.isBlank()) {
            throw new InpatientRejection("summary_unconfigured", 503);
        }
        return HttpRequest.newBuilder(URI.create(baseUrl + path))
                .timeout(timeout)
                .header("X-Service-Token", serviceToken)
                .header("Accept", "application/json");
    }

    private Map<String, Object> read(HttpResponse<String> response) throws Exception {
        if (response.statusCode() >= 400) {
            String code = "summary_rejected";
            try {
                Map<String, Object> body = mapper.readValue(response.body(), new TypeReference<>() {});
                if (body.get("error") instanceof String error && error.matches("[a-z_]{1,40}")) {
                    code = error;
                }
            } catch (Exception ignored) {
                code = "summary_rejected";
            }
            throw new InpatientRejection(code, response.statusCode());
        }
        return mapper.readValue(response.body(), new TypeReference<>() {});
    }

    private static String caseId(String caseId) {
        if (caseId == null || !caseId.matches("sum-[0-9a-f]{12}")) {
            throw new InpatientRejection("not_found", 404);
        }
        return caseId;
    }
}

package lab.healthcare.fhir.externalfhir;

import lab.healthcare.fhir.clinicalread.ClinicalReadException;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;

import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.UUID;
import java.util.regex.Pattern;

/**
 * GET-only reader for one allowlisted FHIR R4 origin. Redirects are not followed.
 * A next-page URL on another host is rejected before any request is sent.
 */
public final class ExternalFhirClient {

    public static final String UCUM = "http://unitsofmeasure.org";
    public static final String VERIFICATION = "https://lab.local/external-fhir/verification";

    private static final String LABORATORY_QUANTITY = "category=laboratory&value-quantity=gt0";
    private static final Pattern ID = Pattern.compile("[A-Za-z0-9\\-.]{1,64}");
    private static final Set<String> SEARCH_TYPES = Set.of("Observation", "DiagnosticReport");
    private static final Set<String> OBSERVATION_STATUS = Set.of(
            "registered", "preliminary", "final", "amended", "corrected",
            "cancelled", "entered-in-error", "unknown");

    private final ExternalFhirProperties properties;
    private final Fetcher fetcher;
    private final ExternalFhirAudit audit;
    private final ObjectMapper json;

    public ExternalFhirClient(ExternalFhirProperties properties, ExternalFhirAudit audit, ObjectMapper json) {
        this(properties, audit, json, null);
    }

    public ExternalFhirClient(
            ExternalFhirProperties properties, ExternalFhirAudit audit, ObjectMapper json, Fetcher fetcher) {
        properties.requireClosed();
        if (!properties.isEnabled()) {
            throw new IllegalStateException("external fhir is disabled");
        }
        this.properties = properties;
        this.audit = audit;
        this.json = json;
        this.fetcher = fetcher == null ? http() : fetcher;
    }

    public JsonNode readCapability() {
        String correlation = correlation();
        JsonNode statement = one(correlation, "CapabilityStatement", "/metadata");
        if (statement == null || !"CapabilityStatement".equals(statement.path("resourceType").asText())
                || !statement.path("fhirVersion").asText("").startsWith("4.0.")) {
            throw ClinicalReadException.external("response_rejected");
        }
        return statement;
    }

    public String discoverPatientId() {
        String correlation = correlation();
        Fetched fetched = send(
                correlation, endpoint("/Observation", LABORATORY_QUANTITY + "&_count=1"), "Observation");
        if (fetched.status() == 404) {
            throw ClinicalReadException.notFound();
        }
        JsonNode bundle = parse(fetched.body());
        JsonNode resource = bundle.path("entry").path(0).path("resource");
        String reference = resource.path("subject").path("reference").asText("");
        int at = reference.lastIndexOf("Patient/");
        if (!"Bundle".equals(bundle.path("resourceType").asText())
                || !"Observation".equals(resource.path("resourceType").asText()) || at < 0) {
            throw ClinicalReadException.external("response_rejected");
        }
        String id = reference.substring(at + "Patient/".length());
        requireId(id);
        return id;
    }

    public JsonNode readPatient(String patientId) {
        requireId(patientId);
        String correlation = correlation();
        JsonNode resource = one(correlation, "Patient", "/Patient/" + encode(patientId));
        if (resource == null || !"Patient".equals(resource.path("resourceType").asText())
                || !patientId.equals(resource.path("id").asText())) {
            throw ClinicalReadException.external("response_rejected");
        }
        return resource;
    }

    public SearchResult search(String resourceType, String patientId) {
        return search(resourceType, patientId, "");
    }

    public SearchResult searchLaboratoryQuantities(String patientId) {
        return search("Observation", patientId, LABORATORY_QUANTITY);
    }

    private SearchResult search(String resourceType, String patientId, String extra) {
        requireId(patientId);
        if (!SEARCH_TYPES.contains(resourceType)) {
            throw ClinicalReadException.invalidRequest();
        }
        String correlation = correlation();
        String path = "/" + resourceType;
        String query = "patient=" + encode(patientId) + "&_count=" + properties.getPageSize()
                + (extra.isBlank() ? "" : "&" + extra);
        List<JsonNode> found = new ArrayList<>();
        String next = null;
        boolean truncated = false;
        for (int page = 0; page < properties.getMaxPages(); page++) {
            URI uri = page == 0 ? endpoint(path, query) : nextUri(next, resourceType, patientId);
            Fetched fetched = send(correlation, uri, resourceType);
            if (fetched.status() == 404) {
                break;
            }
            JsonNode bundle = parse(fetched.body());
            JsonNode entries = bundle.path("entry");
            if (!"Bundle".equals(bundle.path("resourceType").asText())
                    || !"searchset".equals(bundle.path("type").asText())
                    || !(entries.isArray() || entries.isMissingNode() || entries.isNull())) {
                throw ClinicalReadException.external("response_rejected");
            }
            for (JsonNode entry : entries) {
                JsonNode resource = entry.path("resource");
                if (!resource.isObject()) {
                    continue;
                }
                if (accept(resourceType, patientId, resource)) {
                    found.add(resource);
                }
            }
            next = nextLink(bundle);
            if (next == null) {
                break;
            }
            if (page == properties.getMaxPages() - 1) {
                truncated = true;
            }
        }
        return new SearchResult(List.copyOf(found), truncated);
    }

    public record SearchResult(List<JsonNode> resources, boolean truncated) {
    }

    private boolean accept(String resourceType, String patientId, JsonNode resource) {
        if (!resourceType.equals(resource.path("resourceType").asText()) || resource.path("id").asText("").isBlank()) {
            return false;
        }
        if ("Observation".equals(resourceType) && !OBSERVATION_STATUS.contains(resource.path("status").asText())) {
            return false;
        }
        if (!subjectMatches(resource, patientId)) {
            return false;
        }
        if ("Observation".equals(resourceType) && resource instanceof ObjectNode object) {
            tag(object);
        }
        return true;
    }

    private static boolean subjectMatches(JsonNode resource, String patientId) {
        String reference = resource.path("subject").path("reference").asText("");
        String expected = "Patient/" + patientId;
        return expected.equals(reference) || reference.endsWith("/" + expected);
    }

    private static void tag(ObjectNode observation) {
        JsonNode quantity = observation.path("valueQuantity");
        String code = quantityVerified(quantity) ? "quantity-verified" : (
                quantity.isObject() ? "unit-not-verified" : "no-quantity");
        ArrayNodeTag.add(observation, code);
        JsonNode low = observation.path("referenceRange").path(0).path("low");
        JsonNode high = observation.path("referenceRange").path(0).path("high");
        if (low.isObject() || high.isObject()) {
            ArrayNodeTag.add(observation, rangeVerified(quantity, low, high) ? "range-verified" : "range-not-verified");
        }
    }

    private static boolean quantityVerified(JsonNode quantity) {
        if (!quantity.isObject() || !UCUM.equals(quantity.path("system").asText())) {
            return false;
        }
        String code = quantity.path("code").asText("");
        String unit = quantity.path("unit").asText("");
        return !code.isBlank() && quantity.path("value").isNumber()
                && (unit.isBlank() || unit.equals(code));
    }

    private static boolean rangeVerified(JsonNode quantity, JsonNode low, JsonNode high) {
        if (!quantityVerified(quantity) || !low.isObject() || !high.isObject()) {
            return false;
        }
        String code = quantity.path("code").asText();
        if (!UCUM.equals(low.path("system").asText()) || !UCUM.equals(high.path("system").asText())) {
            return false;
        }
        if (!code.equals(low.path("code").asText()) || !code.equals(high.path("code").asText())) {
            return false;
        }
        return low.path("value").isNumber() && high.path("value").isNumber()
                && low.path("value").decimalValue().compareTo(high.path("value").decimalValue()) <= 0;
    }

    private JsonNode one(String correlation, String type, String path) {
        Fetched fetched = send(correlation, endpoint(path, null), type);
        if (fetched.status() == 404) {
            return null;
        }
        return parse(fetched.body());
    }

    private Fetched send(String correlation, URI uri, String type) {
        guard(uri);
        try {
            Fetched fetched = fetcher.get(uri);
            String outcome = outcome(fetched.status());
            audit.record(correlation, uri.getHost(), auditPath(uri.getPath()), fetched.status(), outcome, type, "");
            if (fetched.status() >= 300 && fetched.status() < 400) {
                throw ClinicalReadException.external("redirect_rejected");
            }
            if (fetched.status() == 404) {
                return fetched;
            }
            if (fetched.status() != 200) {
                throw ClinicalReadException.external(outcome);
            }
            if (fetched.body().length > properties.getMaxBytes()) {
                throw ClinicalReadException.external("response_rejected");
            }
            return fetched;
        } catch (ClinicalReadException ex) {
            throw ex;
        } catch (java.net.http.HttpTimeoutException ex) {
            audit.record(correlation, uri.getHost(), auditPath(uri.getPath()), 0, "timeout", type, "");
            throw ClinicalReadException.external("timeout");
        } catch (Exception ex) {
            audit.record(correlation, safeHost(uri), auditPath(uri.getPath()), 0, "source_error", type, "");
            throw ClinicalReadException.external("source_error");
        }
    }

    private static String outcome(int status) {
        return switch (status) {
            case 200 -> "read";
            case 401 -> "unauthorized";
            case 403 -> "forbidden";
            case 404 -> "not_found";
            case 429 -> "rate_limited";
            default -> status >= 300 && status < 400 ? "redirect_rejected" : "source_error";
        };
    }

    private JsonNode parse(byte[] body) {
        try {
            JsonNode node = json.readTree(body);
            if (!node.isObject()) {
                throw ClinicalReadException.external("response_rejected");
            }
            return node;
        } catch (ClinicalReadException ex) {
            throw ex;
        } catch (Exception ex) {
            throw ClinicalReadException.external("response_rejected");
        }
    }

    private URI endpoint(String path, String query) {
        String base = properties.getBaseUrl().replaceAll("/$", "");
        return guard(URI.create(base + path + (query == null ? "" : "?" + query)));
    }

    private URI nextUri(String next, String resourceType, String patientId) {
        URI uri = guard(URI.create(next));
        if (!("/" + resourceType).equals(uri.getPath())) {
            throw ClinicalReadException.external("response_rejected");
        }
        String query = uri.getRawQuery() == null ? "" : uri.getRawQuery();
        String lowered = query.toLowerCase(java.util.Locale.ROOT);
        if (query.contains("://") || lowered.contains("%3a%2f%2f") || query.contains("@") || !samePatient(query, patientId)) {
            throw ClinicalReadException.external("response_rejected");
        }
        return uri;
    }

    private String nextLink(JsonNode bundle) {
        for (JsonNode link : bundle.path("link")) {
            if ("next".equals(link.path("relation").asText())) {
                String url = link.path("url").asText("");
                return url.isBlank() ? null : url;
            }
        }
        return null;
    }

    private URI guard(URI uri) {
        String host = uri.getHost() == null ? "" : uri.getHost();
        if (!"https".equals(uri.getScheme()) || uri.getUserInfo() != null || uri.getFragment() != null
                || uri.getPort() != -1 || !properties.getAllowedHost().equals(host)
                || host.matches("[0-9.]+") || host.contains(":")) {
            throw ClinicalReadException.external("response_rejected");
        }
        return uri;
    }

    private Fetcher http() {
        HttpClient client = HttpClient.newBuilder()
                .connectTimeout(Duration.ofMillis(properties.getConnectTimeoutMillis()))
                .followRedirects(HttpClient.Redirect.NEVER)
                .build();
        return uri -> {
            HttpRequest request = HttpRequest.newBuilder(uri)
                    .timeout(Duration.ofMillis(properties.getReadTimeoutMillis()))
                    .header("Accept", "application/fhir+json")
                    .GET()
                    .build();
            HttpResponse<byte[]> response = client.send(request, HttpResponse.BodyHandlers.ofByteArray());
            return new Fetched(response.statusCode(), response.body());
        };
    }

    private static String auditPath(String path) {
        if (path == null || path.isBlank()) {
            return "";
        }
        String[] parts = path.split("/");
        if (parts.length < 2 || parts[1].isBlank()) {
            return "";
        }
        return "/" + parts[1];
    }

    private static boolean samePatient(String query, String patientId) {
        String encoded = encode(patientId);
        boolean matched = false;
        for (String part : query.split("&")) {
            if (!part.startsWith("patient=")) {
                continue;
            }
            if (!part.equals("patient=" + encoded) && !part.equals("patient=Patient%2F" + encoded)) {
                return false;
            }
            matched = true;
        }
        return matched;
    }

    private static void requireId(String patientId) {
        if (patientId == null || !ID.matcher(patientId).matches() || patientId.contains("..")) {
            throw ClinicalReadException.invalidRequest();
        }
    }

    private static String encode(String value) {
        return URLEncoder.encode(value, StandardCharsets.UTF_8);
    }

    private static String correlation() {
        return "EXT-" + UUID.randomUUID().toString().replace("-", "").substring(0, 16).toUpperCase();
    }

    private static String safeHost(URI uri) {
        return uri.getHost() == null ? "" : uri.getHost();
    }

    public interface Fetcher {
        Fetched get(URI uri) throws Exception;
    }

    public record Fetched(int status, byte[] body) {
    }

    private static final class ArrayNodeTag {
        private ArrayNodeTag() {
        }

        private static void add(ObjectNode observation, String code) {
            ObjectNode meta = observation.has("meta") && observation.get("meta").isObject()
                    ? (ObjectNode) observation.get("meta")
                    : observation.putObject("meta");
            com.fasterxml.jackson.databind.node.ArrayNode tags = meta.has("tag") && meta.get("tag").isArray()
                    ? (com.fasterxml.jackson.databind.node.ArrayNode) meta.get("tag")
                    : meta.putArray("tag");
            ObjectNode tag = tags.addObject();
            tag.put("system", VERIFICATION);
            tag.put("code", code);
        }
    }
}

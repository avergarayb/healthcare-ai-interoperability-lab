package lab.healthcare.fhir.externalfhir;

import lab.healthcare.fhir.clinicalread.ClinicalReadException;
import lab.healthcare.fhir.exchange.ExchangeStore;
import lab.healthcare.fhir.exchange.OrderCorrelation;
import lab.healthcare.fhir.federation.ClinicalConnector;
import lab.healthcare.fhir.federation.FederationProperties;
import lab.healthcare.fhir.federation.FederationService;
import lab.healthcare.fhir.federation.audit.FederationSecurityAudit;
import lab.healthcare.fhir.interop.InteropSourcesProperties;
import lab.healthcare.fhir.interop.SourceRegistry;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfSystemProperty;
import org.junit.jupiter.api.io.TempDir;

import java.net.URI;
import java.net.http.HttpTimeoutException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.ArrayDeque;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class ExternalFhirClientTest {

    private static final String PATIENT = "syn-patient-1";
    private static final String SYSTEM = "https://lab.local/external-fhir/patient";
    private final ObjectMapper json = new ObjectMapper();

    @TempDir
    Path temp;

    @Test
    void checkedInGrantDoesNotNameTheSandbox() throws Exception {
        String yml = Files.readString(Path.of("src/main/resources/application.yml"));
        int grants = yml.indexOf("  grants:");
        int external = yml.indexOf("external-fhir:");
        assertThat(grants).isGreaterThan(0);
        assertThat(external).isGreaterThan(grants);
        assertThat(yml.substring(grants, external)).doesNotContain("smart-sandbox");
        assertThat(yml).contains("enabled: ${EXTERNAL_FHIR_ENABLED:false}");
    }

    @Test
    void verifiedQuantityIsTaggedAndAForeignSubjectIsDropped() throws Exception {
        Script script = new Script();
        script.page("/Observation", bundle(observation(PATIENT, "obs-verified", "2085-9", "69.3", "mg/dL", true),
                observation(PATIENT, "obs-plain", "787-2", "83.744", "fL", false),
                observation("other-patient", "obs-foreign", "2085-9", "1", "mg/dL", true)));
        ExternalFhirClient client = client(script);

        List<JsonNode> found = client.search("Observation", PATIENT).resources();

        assertThat(found).extracting(item -> item.path("id").asText()).containsExactly("obs-verified", "obs-plain");
        assertThat(codes(found.get(0))).contains("quantity-verified", "range-verified");
        assertThat(codes(found.get(1))).contains("unit-not-verified");
        assertThat(auditText()).doesNotContain("83.744").doesNotContain("name")
                .doesNotContain(PATIENT).doesNotContain("obs-verified").contains("/Observation");
    }

    @Test
    void absoluteSubjectMustUseTheAllowlistedHost() {
        Script script = new Script();
        ObjectNode same = observation(PATIENT, "obs-absolute", "2085-9", "69.3", "mg/dL", true);
        same.putObject("subject").put("reference", "https://r4.smarthealthit.org/Patient/" + PATIENT);
        ObjectNode foreign = observation(PATIENT, "obs-other-host", "2085-9", "1", "mg/dL", true);
        foreign.putObject("subject").put("reference", "https://evil.example/Patient/" + PATIENT);
        script.page("/Observation", bundle(same, foreign));

        List<JsonNode> found = client(script).search("Observation", PATIENT).resources();

        assertThat(found).extracting(item -> item.path("id").asText()).containsExactly("obs-absolute");
    }

    @Test
    void nextPageMustStayOnTheAllowlistedHost() {
        Script script = new Script();
        ObjectNode page = bundle(observation(PATIENT, "obs-1", "2085-9", "69.3", "mg/dL", true));
        page.putArray("link").addObject().put("relation", "next").put("url", "https://evil.example/Observation?patient=" + PATIENT);
        script.page("/Observation", page);

        assertThatThrownBy(() -> client(script).search("Observation", PATIENT))
                .isInstanceOfSatisfying(ClinicalReadException.class, error -> assertThat(error.code()).isEqualTo("response_rejected"));
        assertThat(script.seen).hasSize(1);
    }

    @Test
    void nextPageCannotNameALongerPatientId() {
        Script script = new Script();
        ObjectNode page = bundle(observation(PATIENT, "obs-1", "2085-9", "69.3", "mg/dL", true));
        page.putArray("link").addObject().put("relation", "next")
                .put("url", "https://r4.smarthealthit.org/Observation?patient=" + PATIENT + "-other");
        script.page("/Observation", page);

        assertThatThrownBy(() -> client(script).search("Observation", PATIENT))
                .isInstanceOfSatisfying(ClinicalReadException.class, error -> assertThat(error.code()).isEqualTo("response_rejected"));
        assertThat(script.seen).hasSize(1);
    }

    @Test
    void serverContinuationWithoutAPatientParameterIsRead() {
        Script script = new Script();
        ObjectNode page = bundle(observation(PATIENT, "obs-1", "2085-9", "69.3", "mg/dL", true));
        page.putArray("link").addObject().put("relation", "next")
                .put("url", "https://r4.smarthealthit.org/?_getpages=opaque&_count=20");
        script.page("/Observation", page);
        script.page("/", bundle(observation(PATIENT, "obs-2", "787-2", "80", "fL", true)));

        ExternalFhirClient.SearchResult found = client(script).search("Observation", PATIENT);

        assertThat(found.resources()).extracting(item -> item.path("id").asText()).containsExactly("obs-1", "obs-2");
        assertThat(found.truncated()).isFalse();
        assertThat(script.seen).hasSize(2);
    }

    @Test
    void secondPageOnTheSameHostIsReadOnce() {
        Script script = new Script();
        ObjectNode page = bundle(observation(PATIENT, "obs-1", "2085-9", "69.3", "mg/dL", true));
        page.putArray("link").addObject().put("relation", "next")
                .put("url", "https://r4.smarthealthit.org/Observation?patient=" + PATIENT + "&_getpagesoffset=20");
        script.page("/Observation", page);
        ObjectNode second = bundle(observation(PATIENT, "obs-2", "787-2", "80", "fL", true));
        second.putArray("link").addObject().put("relation", "next")
                .put("url", "https://r4.smarthealthit.org/Observation?patient=" + PATIENT + "&_getpagesoffset=40");
        script.page("/Observation", second);

        ExternalFhirClient.SearchResult found = client(script).search("Observation", PATIENT);

        assertThat(found.resources()).extracting(item -> item.path("id").asText()).containsExactly("obs-1", "obs-2");
        assertThat(found.truncated()).isTrue();
        assertThat(script.seen).hasSize(2);
    }

    @Test
    void redirectAndHttpFailuresAreExplicit() {
        assertStatus(302, "redirect_rejected");
        assertStatus(401, "unauthorized");
        assertStatus(403, "forbidden");
        assertStatus(429, "rate_limited");
        assertStatus(500, "source_error");
    }

    @Test
    void timeoutIsNotRetried() {
        Script script = new Script();
        script.fail(new HttpTimeoutException("slow"));

        assertThatThrownBy(() -> client(script).readPatient(PATIENT))
                .isInstanceOfSatisfying(ClinicalReadException.class, error -> assertThat(error.code()).isEqualTo("timeout"));
        assertThat(script.seen).hasSize(1);
    }

    @Test
    void explicitLinkFeedsFederationAndAMissingLinkDoesNotCallTheSandbox() throws Exception {
        Script script = new Script();
        script.page("/Patient/" + PATIENT, patient(PATIENT));
        script.page("/Patient/" + PATIENT, patient(PATIENT));
        script.page("/Observation", bundle(observation(PATIENT, "obs-verified", "2085-9", "69.3", "mg/dL", true)));
        ExternalPatientLinkStore links = new ExternalPatientLinkStore(temp.resolve("links.sqlite"), "smart-sandbox");
        links.assign("mini-his", SYSTEM, "EXT-PAT-001", PATIENT);
        FederationService service = federation(new ExternalFhirConnector(client(script)), links);

        JsonNode linked = service.query("mini-his", request(List.of("smart-sandbox"), "EXT-PAT-001", SYSTEM));

        assertThat(linked.path("status").asText()).isEqualTo("complete");
        assertThat(linked.path("contractVersion").asText()).isEqualTo("clinical-federation-v1");
        assertThat(linked.path("sources")).hasSize(1);
        assertThat(linked.path("sources").get(0).path("sourceKey").asText()).isEqualTo("smart-sandbox");
        assertThat(linked.path("entries").get(1).path("resource").path("id").asText()).isEqualTo("obs-verified");
        assertThat(linked.path("entries").get(1).path("fullUrl").asText())
                .isEqualTo("https://r4.smarthealthit.org/Observation/obs-verified");

        Script untouched = new Script();
        FederationService unresolved = federation(new ExternalFhirConnector(client(untouched)), links);
        JsonNode missing = unresolved.query("mini-his", request(List.of("smart-sandbox"), "EXT-PAT-002", SYSTEM));
        assertThat(missing.path("sources").get(0).path("outcome").asText()).isEqualTo("identity_unresolved");
        assertThat(untouched.seen).isEmpty();
    }

    @Test
    void omittedSourcesDoNotSelectTheSandbox() {
        Script script = new Script();
        ClinicalConnector local = new ClinicalConnector() {
            @Override
            public String key() {
                return "mini-his";
            }

            @Override
            public String resolvePatient(String identifierSystem, String identifierValue) {
                return "MHS-PAT-001";
            }

            @Override
            public Collected collect(String resourceType, String patientId) {
                return new Collected(List.of(patient("MHS-PAT-001")), false);
            }
        };
        ExternalPatientLinkStore links = new ExternalPatientLinkStore(temp.resolve("links.sqlite"), "smart-sandbox");
        FederationService service = federation(List.of(local, new ExternalFhirConnector(client(script))), links);

        JsonNode body = service.query("mini-his", request(null, "MHS-PAT-001", "https://lab.local/mini-his/patient"));

        assertThat(body.path("sources")).extracting(item -> item.path("sourceKey").asText())
                .containsExactly("mini-his", "mini-lis");
        assertThat(script.seen).isEmpty();
    }

    @Test
    @EnabledIfSystemProperty(named = "external.fhir.live", matches = "true")
    void liveSandboxReadUsesTheAdapter() throws Exception {
        ExternalFhirProperties properties = properties();
        properties.setReadTimeoutMillis(20000);
        properties.setConnectTimeoutMillis(5000);
        properties.setMaxPages(1);
        properties.setPageSize(5);
        ExternalFhirClient client = new ExternalFhirClient(properties, audit(), json);
        JsonNode statement = client.readCapability();
        String patientId = client.discoverPatientId();
        List<JsonNode> observations = client.searchLaboratoryQuantities(patientId).resources();
        List<JsonNode> reports = client.search("DiagnosticReport", patientId).resources();
        ObjectNode evidence = json.createObjectNode();
        evidence.put("host", ExternalFhirProperties.ALLOWED_HOST);
        evidence.put("fhirVersion", statement.path("fhirVersion").asText());
        evidence.put("patientId", patientId);
        evidence.put("observationCount", observations.size());
        evidence.put("diagnosticReportCount", reports.size());
        var verified = evidence.putArray("verified");
        observations.stream().limit(3).forEach(item -> {
            ObjectNode row = verified.addObject();
            row.put("id", item.path("id").asText());
            row.put("status", item.path("status").asText());
            row.put("code", item.path("code").path("coding").path(0).path("code").asText());
            row.put("unit", item.path("valueQuantity").path("code").asText());
            row.put("subject", item.path("subject").path("reference").asText());
        });
        Path output = Path.of(System.getProperty("java.io.tmpdir"), "interop-001-evidence.json");
        Files.writeString(output, json.writeValueAsString(evidence));

        assertThat(statement.path("fhirVersion").asText()).startsWith("4.0.");
        assertThat(patientId).isNotBlank();
        assertThat(observations).isNotEmpty();
        assertThat(observations).allSatisfy(item -> assertThat(item.path("subject").path("reference").asText())
                .endsWith("Patient/" + patientId));
        assertThat(observations).anySatisfy(item -> assertThat(codes(item)).contains("quantity-verified"));
    }

    private void assertStatus(int status, String code) {
        Script script = new Script();
        script.page("/Patient/" + PATIENT, status, "{}");
        assertThatThrownBy(() -> client(script).readPatient(PATIENT))
                .isInstanceOfSatisfying(ClinicalReadException.class, error -> assertThat(error.code()).isEqualTo(code));
        assertThat(script.seen).hasSize(1);
    }

    private ExternalFhirClient client(Script script) {
        return new ExternalFhirClient(properties(), audit(), json, script);
    }

    private ExternalFhirProperties properties() {
        ExternalFhirProperties properties = new ExternalFhirProperties();
        properties.setEnabled(true);
        properties.requireClosed();
        return properties;
    }

    private ExternalFhirAudit audit() {
        return new ExternalFhirAudit(temp.resolve("audit.sqlite"));
    }

    private String auditText() throws Exception {
        try (Connection connection = DriverManager.getConnection("jdbc:sqlite:" + temp.resolve("audit.sqlite"));
                ResultSet rows = connection.createStatement().executeQuery("SELECT path, outcome, resource_id FROM external_fhir_request")) {
            StringBuilder text = new StringBuilder();
            while (rows.next()) {
                text.append(rows.getString(1)).append(' ').append(rows.getString(2)).append(' ').append(rows.getString(3)).append('\n');
            }
            return text.toString();
        }
    }

    private FederationService federation(ClinicalConnector connector, ExternalPatientLinkStore links) {
        return federation(List.of(connector), links);
    }

    private FederationService federation(List<ClinicalConnector> connectors, ExternalPatientLinkStore links) {
        InteropSourcesProperties sources = new InteropSourcesProperties();
        InteropSourcesProperties.SourceProperties local = new InteropSourcesProperties.SourceProperties();
        local.setOrganizationId("org-mini-his");
        local.setDisplayName("Mini HIS");
        local.setBaseUrl("http://127.0.0.1:8095");
        local.setCapabilities(List.of("patient", "observation"));
        sources.getSources().put("mini-his", local);
        SourceRegistry registry = new SourceRegistry(sources).withAdditional(properties().descriptor());
        FederationProperties federation = new FederationProperties();
        federation.setMaxSources(4);
        federation.setMaxEntries(100);
        federation.setQueryBudgetSeconds(20);
        federation.getGrants().put("mini-his", List.of("mini-his", "mini-lis", "smart-sandbox"));
        return new FederationService(
                registry, new UnusedExchange(), connectors, federation, json,
                new FederationSecurityAudit(event -> {}, Clock.fixed(Instant.parse("2026-11-17T12:00:00Z"), ZoneOffset.UTC)),
                links, Set.of("smart-sandbox"));
    }

    private ObjectNode request(List<String> sources, String patientId, String system) {
        ObjectNode body = json.createObjectNode();
        body.put("requestingOrganizationId", "org-mini-his");
        body.put("correlationId", "FED-0123456789ABCDEF");
        ObjectNode patient = body.putObject("patient");
        patient.put("systemKey", "mini-his");
        patient.put("identifierSystem", system);
        patient.put("identifierValue", patientId);
        if (sources != null) {
            var array = body.putArray("sources");
            sources.forEach(array::add);
        }
        body.putArray("resourceTypes").add("Patient").add("Observation");
        return body;
    }

    private ObjectNode bundle(ObjectNode... resources) {
        ObjectNode bundle = json.createObjectNode();
        bundle.put("resourceType", "Bundle");
        bundle.put("type", "searchset");
        var entries = bundle.putArray("entry");
        for (ObjectNode resource : resources) {
            entries.addObject().set("resource", resource);
        }
        return bundle;
    }

    private ObjectNode patient(String id) {
        ObjectNode resource = json.createObjectNode();
        resource.put("resourceType", "Patient");
        resource.put("id", id);
        return resource;
    }

    private ObjectNode observation(String patientId, String id, String code, String value, String unit, boolean ucum) {
        ObjectNode resource = json.createObjectNode();
        resource.put("resourceType", "Observation");
        resource.put("id", id);
        resource.put("status", "final");
        resource.putObject("subject").put("reference", "Patient/" + patientId);
        resource.putObject("code").putArray("coding").addObject().put("code", code);
        ObjectNode quantity = resource.putObject("valueQuantity");
        quantity.put("value", Double.parseDouble(value));
        quantity.put("unit", unit);
        if (ucum) {
            quantity.put("system", ExternalFhirClient.UCUM);
            quantity.put("code", unit);
            ObjectNode range = resource.putArray("referenceRange").addObject();
            range.putObject("low").put("value", 40).put("system", ExternalFhirClient.UCUM).put("code", unit);
            range.putObject("high").put("value", 60).put("system", ExternalFhirClient.UCUM).put("code", unit);
        }
        return resource;
    }

    private static List<String> codes(JsonNode resource) {
        List<String> found = new ArrayList<>();
        resource.path("meta").path("tag").forEach(tag -> found.add(tag.path("code").asText()));
        return found;
    }

    private final class Script implements ExternalFhirClient.Fetcher {
        private final Map<String, ArrayDeque<ExternalFhirClient.Fetched>> pages = new LinkedHashMap<>();
        private final List<URI> seen = new ArrayList<>();
        private Exception failure;

        private void page(String path, ObjectNode body) {
            page(path, 200, body.toString());
        }

        private void page(String path, int status, String body) {
            pages.computeIfAbsent(path, key -> new ArrayDeque<>())
                    .add(new ExternalFhirClient.Fetched(status, body.getBytes()));
        }

        private void fail(Exception failure) {
            this.failure = failure;
        }

        @Override
        public ExternalFhirClient.Fetched get(URI uri) throws Exception {
            seen.add(uri);
            if (failure != null) {
                throw failure;
            }
            String key = uri.getPath() == null || uri.getPath().isEmpty() ? "/" : uri.getPath();
            ArrayDeque<ExternalFhirClient.Fetched> queue = pages.get(key);
            if (queue == null || queue.isEmpty()) {
                throw new IllegalStateException("unexpected path " + uri.getPath());
            }
            return queue.remove();
        }
    }

    private static final class UnusedExchange implements ExchangeStore {
        @Override
        public Optional<String> findPatientLink(String sourceSystem, String identifierSystem, String identifierValue, String destinationSystem) {
            return Optional.empty();
        }

        @Override
        public void savePatientLink(String sourceSystem, String identifierSystem, String identifierValue, String destinationSystem, String destinationPatientId) {
            throw new UnsupportedOperationException();
        }

        @Override
        public Optional<OrderCorrelation> findOrder(String sourceSystem, String sourceOrganizationId, String sourceOrderId, String destinationSystem) {
            return Optional.empty();
        }

        @Override
        public Optional<OrderCorrelation> findOwnedOrder(String sourceSystem, String sourceOrderId) {
            return Optional.empty();
        }

        @Override
        public void insert(OrderCorrelation correlation) {
            throw new UnsupportedOperationException();
        }

        @Override
        public void updateDelivery(String correlationId, String deliveryState, String errorCode, String destinationOrderId, String destinationPatientId) {
            throw new UnsupportedOperationException();
        }

        @Override
        public Optional<OrderCorrelation> findByDestinationOrder(String destinationSystem, String destinationOrderId) {
            return Optional.empty();
        }

        @Override
        public boolean saveHl7Observation(String messageControlId, String destinationOrderId, String sourceOrderId, String externalResultId, String observationJson) {
            throw new UnsupportedOperationException();
        }

        @Override
        public List<String> hl7Observations(String destinationOrderId) {
            return List.of();
        }
    }
}

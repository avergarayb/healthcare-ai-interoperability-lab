package lab.healthcare.fhir.federation;

import lab.healthcare.fhir.clinicalread.ClinicalReadException;
import lab.healthcare.fhir.exchange.ExchangeStore;
import lab.healthcare.fhir.federation.audit.FederationSecurityAudit;
import lab.healthcare.fhir.federation.audit.FederationSecurityAuditEvent;
import lab.healthcare.fhir.federation.audit.FederationSecurityAuditUnavailable;
import lab.healthcare.fhir.interop.SourceRegistry;
import lab.healthcare.fhir.interop.SourceRegistry.SourceDescriptor;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.time.Duration;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.regex.Pattern;

/**
 * Reads several authorized sources through existing connectors. Clinical Read
 * remains a single-source API. This service does not match patients by name,
 * birth date, or text similarity.
 */
public class FederationService {

    static final String CONTRACT_VERSION = "clinical-federation-v1";

    private static final Logger log = LoggerFactory.getLogger(FederationService.class);
    private static final Pattern KEY = Pattern.compile("[a-z0-9\\-]{1,64}");
    private static final Pattern ID = Pattern.compile("[A-Za-z0-9\\-.]{1,64}");
    private static final Pattern SYSTEM = Pattern.compile("https://[A-Za-z0-9./_\\-]{1,200}");
    private static final Pattern CORRELATION = Pattern.compile("[A-Za-z0-9\\-.]{8,64}");
    private static final Pattern RELATIVE_REFERENCE = Pattern.compile(
            "(Patient|Encounter|Observation|Appointment|ServiceRequest|DiagnosticReport|Organization|Practitioner)/[A-Za-z0-9\\-.]{1,64}");
    private static final List<String> RESOURCE_TYPES = List.of(
            "Patient", "Encounter", "Observation", "Appointment", "ServiceRequest", "DiagnosticReport");
    private static final Map<String, String> CAPABILITY = Map.of(
            "Patient", "patient",
            "Encounter", "encounter",
            "Observation", "observation",
            "Appointment", "appointment",
            "ServiceRequest", "service-request",
            "DiagnosticReport", "diagnostic-report");

    private final SourceRegistry registry;
    private final ExchangeStore store;
    private final Map<String, ClinicalConnector> connectors;
    private final FederationProperties properties;
    private final ObjectMapper json;
    private final FederationSecurityAudit securityAudit;

    public FederationService(
            SourceRegistry registry,
            ExchangeStore store,
            List<ClinicalConnector> connectors,
            FederationProperties properties,
            ObjectMapper json,
            FederationSecurityAudit securityAudit) {
        this.registry = registry;
        this.store = store;
        this.connectors = new LinkedHashMap<>();
        for (ClinicalConnector connector : connectors) {
            this.connectors.put(connector.key(), connector);
        }
        this.properties = properties;
        this.json = json;
        this.securityAudit = securityAudit;
    }

    public JsonNode query(String callerSystem, JsonNode request) {
        if (callerSystem == null || callerSystem.isBlank()) {
            authenticationDenied("participant_not_authenticated");
            throw FederationException.forbidden("unauthenticated");
        }
        Requested requested = parse(request);
        SourceDescriptor caller = registry.find(callerSystem).orElse(null);
        if (caller == null) {
            authorizationDenied(
                    callerSystem,
                    null,
                    "participant_not_registered",
                    requested.correlationId());
            throw FederationException.forbidden("unauthenticated");
        }
        if (!caller.organizationId().equals(requested.organizationId())) {
            authorizationDenied(
                    caller.key(),
                    caller.organizationId(),
                    "organization_not_authorized",
                    requested.correlationId());
            throw FederationException.forbidden("organization_mismatch");
        }
        if (!caller.key().equals(requested.patientSystemKey())) {
            authorizationDenied(
                    caller.key(),
                    caller.organizationId(),
                    "caller_system_not_authorized",
                    requested.correlationId());
            throw FederationException.forbidden("identity_system_mismatch");
        }
        List<String> sources;
        try {
            sources = select(caller.key(), requested.sources());
        } catch (FederationException ex) {
            if ("source_not_authorized".equals(ex.code())) {
                authorizationDenied(
                        caller.key(),
                        caller.organizationId(),
                        "source_not_granted",
                        requested.correlationId());
            }
            throw ex;
        }
        FederationSecurityAuditEvent allowed = allowed(
                caller.key(), caller.organizationId(), requested.correlationId());
        String auditCorrelationId = allowed.correlationId();
        long deadline = System.nanoTime() + Duration.ofSeconds(Math.max(properties.getQueryBudgetSeconds(), 0)).toNanos();
        ArrayNode sourceNodes = json.createArrayNode();
        ArrayNode entries = json.createArrayNode();
        Set<String> identityKeys = new LinkedHashSet<>();
        Set<String> provenanceKeys = new LinkedHashSet<>();
        boolean truncated = false;
        int complete = 0;
        for (String sourceKey : sources) {
            if (entries.size() >= properties.getMaxEntries()) {
                sourceNodes.add(sourceNode(sourceKey, organizationOf(sourceKey), "limit_reached", 0, null));
                continue;
            }
            SourceResult result = readSource(requested, sourceKey, deadline, entries, identityKeys, provenanceKeys);
            truncated = truncated || result.truncated();
            if ("complete".equals(result.outcome())) {
                complete++;
            }
            sourceNodes.add(sourceNode(sourceKey, result.organizationId(), result.outcome(), result.count(), result.errorCode()));
            log.info(
                    "federation_source correlation={} source={} outcome={} error={}",
                    auditCorrelationId, sourceKey, result.outcome(), result.errorCode() == null ? "" : result.errorCode());
        }
        String status = statusOf(complete, sourceNodes.size(), truncated);
        ObjectNode body = json.createObjectNode();
        body.put("contractVersion", CONTRACT_VERSION);
        body.put("correlationId", requested.correlationId());
        body.put("requestingOrganizationId", requested.organizationId());
        body.put("callerSystem", caller.key());
        body.put("status", status);
        body.put("truncated", truncated || entries.size() >= properties.getMaxEntries());
        body.set("sources", sourceNodes);
        body.set("entries", entries);
        log.info(
                "federation_query correlation={} caller={} status={} sources={}",
                auditCorrelationId,
                caller.key(),
                status,
                sourceNodes.size());
        return body;
    }

    private void authenticationDenied(String reasonCode) {
        try {
            securityAudit.authenticationDenied(reasonCode);
        } catch (FederationSecurityAuditUnavailable ex) {
            log.error("federation_security_audit_unavailable decision=authentication_denied", ex);
            throw FederationException.unavailable("audit_unavailable");
        }
    }

    private void authorizationDenied(
            String callerSystem, String organizationId, String reasonCode, String correlationId) {
        try {
            securityAudit.authorizationDenied(callerSystem, organizationId, reasonCode, correlationId);
        } catch (FederationSecurityAuditUnavailable ex) {
            log.error("federation_security_audit_unavailable decision=authorization_denied", ex);
            throw FederationException.unavailable("audit_unavailable");
        }
    }

    private FederationSecurityAuditEvent allowed(
            String callerSystem, String organizationId, String correlationId) {
        try {
            return securityAudit.allowed(callerSystem, organizationId, correlationId);
        } catch (FederationSecurityAuditUnavailable ex) {
            log.error("federation_security_audit_unavailable decision=allowed", ex);
            throw FederationException.unavailable("audit_unavailable");
        }
    }

    private SourceResult readSource(
            Requested requested,
            String sourceKey,
            long deadline,
            ArrayNode entries,
            Set<String> identityKeys,
            Set<String> provenanceKeys) {
        SourceDescriptor descriptor = registry.find(sourceKey).orElse(null);
        String organizationId = descriptor == null ? "" : descriptor.organizationId();
        if (descriptor == null) {
            return new SourceResult(organizationId, "not_registered", 0, null, false);
        }
        ClinicalConnector connector = connectors.get(sourceKey);
        if (connector == null) {
            return new SourceResult(organizationId, "connector_unavailable", 0, null, false);
        }
        List<String> types = supported(descriptor, requested.resourceTypes());
        if (types.isEmpty()) {
            return new SourceResult(organizationId, "capability_unsupported", 0, null, false);
        }
        if (System.nanoTime() >= deadline) {
            return new SourceResult(organizationId, "unavailable", 0, "timeout", false);
        }
        String patientId;
        try {
            patientId = resolvePatient(requested, sourceKey, connector);
        } catch (ClinicalReadException ex) {
            if ("not_found".equals(ex.code()) || "invalid_request".equals(ex.code())) {
                return new SourceResult(organizationId, "identity_unresolved", 0, null, false);
            }
            return new SourceResult(organizationId, "unavailable", 0, ex.code(), false);
        } catch (RuntimeException ex) {
            return new SourceResult(organizationId, "unavailable", 0, "source_error", false);
        }
        if (patientId == null || patientId.isBlank()) {
            return new SourceResult(organizationId, "identity_unresolved", 0, null, false);
        }
        if (!sourceKey.equals(requested.patientSystemKey())) {
            try {
                connector.collect("Patient", patientId);
            } catch (ClinicalReadException ex) {
                if ("not_found".equals(ex.code())) {
                    return new SourceResult(organizationId, "identity_unresolved", 0, null, false);
                }
                return new SourceResult(organizationId, "unavailable", 0, ex.code(), false);
            } catch (RuntimeException ex) {
                return new SourceResult(organizationId, "unavailable", 0, "source_error", false);
            }
        }
        ArrayNode local = json.createArrayNode();
        Set<String> localIdentity = new LinkedHashSet<>();
        Set<String> localProvenance = new LinkedHashSet<>();
        boolean truncated = false;
        try {
            for (String type : types) {
                if (entries.size() + local.size() >= properties.getMaxEntries()) {
                    truncated = true;
                    break;
                }
                ClinicalConnector.Collected collected = connector.collect(type, patientId);
                truncated = truncated || collected.truncated();
                for (JsonNode resource : collected.resources()) {
                    if (entries.size() + local.size() >= properties.getMaxEntries()) {
                        truncated = true;
                        break;
                    }
                    accept(local, descriptor, resource, identityKeys, provenanceKeys, localIdentity, localProvenance);
                }
            }
        } catch (ClinicalReadException ex) {
            if ("not_found".equals(ex.code())) {
                return new SourceResult(organizationId, "identity_unresolved", 0, null, false);
            }
            return new SourceResult(organizationId, "unavailable", 0, ex.code(), false);
        } catch (RuntimeException ex) {
            return new SourceResult(organizationId, "unavailable", 0, "source_error", false);
        }
        local.forEach(entries::add);
        identityKeys.addAll(localIdentity);
        provenanceKeys.addAll(localProvenance);
        return new SourceResult(organizationId, "complete", local.size(), null, truncated);
    }

    private String resolvePatient(Requested requested, String sourceKey, ClinicalConnector connector) {
        if (sourceKey.equals(requested.patientSystemKey())) {
            return connector.resolvePatient(requested.identifierSystem(), requested.identifierValue());
        }
        return store.findPatientLink(
                requested.patientSystemKey(),
                requested.identifierSystem(),
                requested.identifierValue(),
                sourceKey).orElse(null);
    }

    private void accept(
            ArrayNode local,
            SourceDescriptor descriptor,
            JsonNode resource,
            Set<String> identityKeys,
            Set<String> provenanceKeys,
            Set<String> localIdentity,
            Set<String> localProvenance) {
        if (!resource.isObject() || resource.path("resourceType").asText("").isBlank() || resource.path("id").asText("").isBlank()) {
            throw ClinicalReadException.invalidSource();
        }
        String type = resource.path("resourceType").asText();
        String id = resource.path("id").asText();
        String identity = descriptor.key() + "\n" + type + "\n" + id;
        if (identityKeys.contains(identity) || localIdentity.contains(identity)) {
            return;
        }
        String metaSource = resource.path("meta").path("source").asText("");
        List<String> provenance = new ArrayList<>();
        JsonNode identifiers = resource.path("identifier");
        if (!metaSource.isBlank() && identifiers.isArray()) {
            for (JsonNode identifier : identifiers) {
                String system = identifier.path("system").asText("");
                String value = identifier.path("value").asText("");
                if (system.isBlank() || value.isBlank()) {
                    continue;
                }
                provenance.add(type + "\n" + metaSource + "\n" + system + "\n" + value);
            }
        }
        for (String key : provenance) {
            if (provenanceKeys.contains(key) || localProvenance.contains(key)) {
                return;
            }
        }
        ObjectNode copy = resource.deepCopy();
        String baseUrl = trimSlash(descriptor.baseUrl());
        rewriteReferences(copy, baseUrl);
        ObjectNode entry = json.createObjectNode();
        entry.put("sourceKey", descriptor.key());
        entry.put("organizationId", descriptor.organizationId());
        entry.put("fullUrl", baseUrl + "/" + type + "/" + id);
        entry.set("resource", copy);
        local.add(entry);
        localIdentity.add(identity);
        localProvenance.addAll(provenance);
    }

    private void rewriteReferences(JsonNode node, String baseUrl) {
        if (node instanceof ObjectNode object) {
            object.properties().forEach(field -> {
                JsonNode child = field.getValue();
                if ("reference".equals(field.getKey()) && child.isTextual()) {
                    String reference = child.asText();
                    if (RELATIVE_REFERENCE.matcher(reference).matches()) {
                        object.put("reference", baseUrl + "/" + reference);
                    }
                } else {
                    rewriteReferences(child, baseUrl);
                }
            });
            return;
        }
        if (node.isArray()) {
            node.forEach(child -> rewriteReferences(child, baseUrl));
        }
    }

    private List<String> select(String caller, List<String> requested) {
        List<String> granted = properties.getGrants().getOrDefault(caller, List.of());
        List<String> chosen = requested == null ? granted : requested;
        if (chosen.isEmpty() || chosen.size() > properties.getMaxSources()) {
            throw FederationException.invalidRequest();
        }
        LinkedHashSet<String> unique = new LinkedHashSet<>();
        for (String source : chosen) {
            if (source == null || !KEY.matcher(source).matches() || !unique.add(source)) {
                throw FederationException.invalidRequest();
            }
        }
        for (String source : unique) {
            if (!granted.contains(source)) {
                throw FederationException.forbidden("source_not_authorized");
            }
        }
        return List.copyOf(unique);
    }

    private static List<String> supported(SourceDescriptor descriptor, List<String> requested) {
        List<String> types = new ArrayList<>();
        for (String type : requested) {
            String capability = CAPABILITY.get(type);
            if (capability != null && descriptor.capabilities().contains(capability)) {
                types.add(type);
            }
        }
        return types;
    }

    private Requested parse(JsonNode request) {
        if (request == null || !request.isObject()) {
            throw FederationException.invalidRequest();
        }
        Set<String> fields = Set.of("requestingOrganizationId", "patient", "sources", "resourceTypes", "correlationId");
        if (!fields.containsAll(fieldNames(request))) {
            throw FederationException.invalidRequest();
        }
        String organizationId = text(request, "requestingOrganizationId");
        JsonNode patient = request.get("patient");
        if (organizationId == null || !ID.matcher(organizationId).matches() || patient == null || !patient.isObject()) {
            throw FederationException.invalidRequest();
        }
        if (!Set.of("systemKey", "identifierSystem", "identifierValue").containsAll(fieldNames(patient))) {
            throw FederationException.invalidRequest();
        }
        String systemKey = text(patient, "systemKey");
        String identifierSystem = text(patient, "identifierSystem");
        String identifierValue = text(patient, "identifierValue");
        if (systemKey == null || !KEY.matcher(systemKey).matches()
                || identifierSystem == null || !SYSTEM.matcher(identifierSystem).matches()
                || identifierValue == null || !ID.matcher(identifierValue).matches()) {
            throw FederationException.invalidRequest();
        }
        List<String> sources = optionalKeys(request.get("sources"));
        List<String> resourceTypes = resourceTypes(request.get("resourceTypes"));
        String correlationId = text(request, "correlationId");
        if (correlationId == null) {
            correlationId = "FED-" + UUID.randomUUID().toString().replace("-", "").substring(0, 16).toUpperCase(Locale.ROOT);
        } else if (!CORRELATION.matcher(correlationId).matches()) {
            throw FederationException.invalidRequest();
        }
        return new Requested(organizationId, systemKey, identifierSystem, identifierValue, sources, resourceTypes, correlationId);
    }

    private List<String> resourceTypes(JsonNode node) {
        if (node == null || node.isNull()) {
            return RESOURCE_TYPES;
        }
        if (!node.isArray() || node.isEmpty()) {
            throw FederationException.invalidRequest();
        }
        LinkedHashSet<String> types = new LinkedHashSet<>();
        for (JsonNode item : node) {
            if (!item.isTextual() || !RESOURCE_TYPES.contains(item.asText()) || !types.add(item.asText())) {
                throw FederationException.invalidRequest();
            }
        }
        List<String> ordered = new ArrayList<>();
        for (String type : RESOURCE_TYPES) {
            if (types.contains(type)) {
                ordered.add(type);
            }
        }
        return List.copyOf(ordered);
    }

    private List<String> optionalKeys(JsonNode node) {
        if (node == null || node.isNull()) {
            return null;
        }
        if (!node.isArray()) {
            throw FederationException.invalidRequest();
        }
        List<String> keys = new ArrayList<>();
        node.forEach(item -> keys.add(item.isTextual() ? item.asText() : null));
        return keys;
    }

    private ObjectNode sourceNode(String sourceKey, String organizationId, String outcome, int count, String errorCode) {
        ObjectNode node = json.createObjectNode();
        node.put("sourceKey", sourceKey);
        node.put("organizationId", organizationId);
        node.put("outcome", outcome);
        node.put("resourceCount", count);
        if (errorCode != null) {
            node.put("error", errorCode);
        }
        return node;
    }

    private String organizationOf(String sourceKey) {
        return registry.find(sourceKey).map(SourceDescriptor::organizationId).orElse("");
    }

    private static String statusOf(int complete, int sources, boolean truncated) {
        if (complete == 0) {
            return "failed";
        }
        if (complete == sources && !truncated) {
            return "complete";
        }
        return "partial";
    }

    private static Set<String> fieldNames(JsonNode node) {
        LinkedHashSet<String> names = new LinkedHashSet<>();
        node.fieldNames().forEachRemaining(names::add);
        return names;
    }

    private static String text(JsonNode node, String field) {
        JsonNode value = node.get(field);
        if (value == null || value.isNull()) {
            return null;
        }
        if (!value.isTextual()) {
            throw FederationException.invalidRequest();
        }
        return value.asText();
    }

    private static String trimSlash(String baseUrl) {
        String value = baseUrl == null ? "" : baseUrl.trim();
        while (value.endsWith("/")) {
            value = value.substring(0, value.length() - 1);
        }
        return value;
    }

    private record Requested(
            String organizationId,
            String patientSystemKey,
            String identifierSystem,
            String identifierValue,
            List<String> sources,
            List<String> resourceTypes,
            String correlationId) {
    }

    private record SourceResult(String organizationId, String outcome, int count, String errorCode, boolean truncated) {
    }
}

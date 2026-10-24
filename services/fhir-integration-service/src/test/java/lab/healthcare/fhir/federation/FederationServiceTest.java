package lab.healthcare.fhir.federation;

import lab.healthcare.fhir.clinicalread.ClinicalReadException;
import lab.healthcare.fhir.clinicalread.ClinicalReadLimits;
import lab.healthcare.fhir.exchange.ExchangeStore;
import lab.healthcare.fhir.exchange.OrderCorrelation;
import lab.healthcare.fhir.federation.audit.FederationSecurityAudit;
import lab.healthcare.fhir.federation.audit.FederationSecurityAuditEvent;
import lab.healthcare.fhir.federation.audit.FederationSecurityAuditUnavailable;
import lab.healthcare.fhir.interop.InteropSourcesProperties;
import lab.healthcare.fhir.interop.SourceRegistry;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;

import org.junit.jupiter.api.Test;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class FederationServiceTest {

    private final ObjectMapper json = new ObjectMapper();

    @Test
    void clinicalReadDefaultStaysLocalHapi() {
        assertThat(ClinicalReadLimits.DESTINATION).isEqualTo("local-hapi");
    }

    @Test
    void explicitLinkReadsBothSourcesAndDoesNotMergeEqualValues() {
        LinkStore store = new LinkStore();
        store.link("mini-his", "https://lab.local/mini-his/patient", "MHS-PAT-001", "mini-lis", "LIS-PAT-1");
        Fake his = patientSource("mini-his", "https://lab.local/mini-his", "MHS-PAT-001");
        his.resources.put("Observation", List.of(
                observation("mini-his", "MHS-RES-1", "GLU", "141", "mmol/L"),
                observation("mini-his", "MHS-RES-1", "GLU", "141", "mmol/L")));
        Fake lis = new Fake("mini-lis");
        lis.resources.put("Patient", List.of(patient("mini-lis", "LIS-PAT-1")));
        lis.resources.put("Observation", List.of(observation("mini-lis", "LIS-RES-1", "GLU", "141", "mmol/L")));
        FederationService service = service(store, List.of(his, lis), 20);

        JsonNode body = service.query("mini-his", request(List.of("mini-his", "mini-lis"), List.of("Patient", "Observation")));

        assertThat(body.path("status").asText()).isEqualTo("complete");
        assertThat(body.path("contractVersion").asText()).isEqualTo("clinical-federation-v1");
        assertThat(entries(body, "mini-his", "Observation")).hasSize(1);
        assertThat(entries(body, "mini-lis", "Observation")).hasSize(1);
        assertThat(entries(body, "mini-his", "Patient")).hasSize(1);
        assertThat(entries(body, "mini-lis", "Patient")).hasSize(1);
        JsonNode hisObservation = entries(body, "mini-his", "Observation").get(0);
        assertThat(hisObservation.path("resource").path("meta").path("source").asText()).isEqualTo("https://lab.local/mini-his");
        assertThat(hisObservation.path("fullUrl").asText()).isEqualTo("http://mini-his.test/Observation/MHS-RES-1");
        assertThat(hisObservation.path("resource").path("subject").path("reference").asText())
                .isEqualTo("http://mini-his.test/Patient/MHS-PAT-001");
        assertThat(hisObservation.path("resource").path("valueQuantity").path("unit").asText()).isEqualTo("mmol/L");
        assertThat(lis.resolveCalls).isZero();
    }

    @Test
    void missingLinkDoesNotSearchTheOtherSource() {
        Fake his = patientSource("mini-his", "https://lab.local/mini-his", "MHS-PAT-001");
        Fake lis = new Fake("mini-lis");
        FederationService service = service(new LinkStore(), List.of(his, lis), 20);

        JsonNode body = service.query("mini-his", request(List.of("mini-his", "mini-lis"), List.of("Patient", "Observation")));

        assertThat(body.path("status").asText()).isEqualTo("partial");
        assertThat(outcome(body, "mini-his")).isEqualTo("complete");
        assertThat(outcome(body, "mini-lis")).isEqualTo("identity_unresolved");
        assertThat(entries(body, "mini-lis", "Patient")).isEmpty();
        assertThat(lis.resolveCalls).isZero();
        assertThat(lis.collectCalls).isZero();
    }

    @Test
    void resolvedPatientWithNoObservationsIsNotAnIdentityMiss() {
        Fake his = patientSource("mini-his", "https://lab.local/mini-his", "MHS-PAT-001");
        FederationService service = service(new LinkStore(), List.of(his), 20);

        JsonNode body = service.query("mini-his", request(List.of("mini-his"), List.of("Observation")));

        assertThat(body.path("status").asText()).isEqualTo("complete");
        assertThat(outcome(body, "mini-his")).isEqualTo("complete");
        assertThat(count(body, "mini-his")).isZero();
        assertThat(body.path("entries")).isEmpty();
    }

    @Test
    void unauthorizedSourceRejectsTheWholeQuery() {
        Fake his = patientSource("mini-his", "https://lab.local/mini-his", "MHS-PAT-001");
        FederationProperties properties = properties(20);
        properties.getGrants().put("mini-his", List.of("mini-his"));
        FederationService service = new FederationService(
                registry(),
                new LinkStore(),
                List.of(his),
                properties,
                json,
                new FederationSecurityAudit(event -> {}));

        assertThatThrownBy(() -> service.query("mini-his", request(List.of("mini-his", "mini-lis"), List.of("Patient"))))
                .isInstanceOf(FederationException.class)
                .extracting("message")
                .isEqualTo("source_not_authorized");
        assertThat(his.resolveCalls).isZero();
    }

    @Test
    void registeredSourceWithoutConnectorIsNotAnEmptyChart() {
        Fake his = patientSource("mini-his", "https://lab.local/mini-his", "MHS-PAT-001");
        FederationService service = service(new LinkStore(), List.of(his), 20);

        JsonNode body = service.query("mini-his", request(List.of("mini-his", "clinic-b"), List.of("Patient")));

        assertThat(body.path("status").asText()).isEqualTo("partial");
        assertThat(outcome(body, "clinic-b")).isEqualTo("connector_unavailable");
        assertThat(count(body, "clinic-b")).isZero();
        assertThat(entries(body, "mini-his", "Patient")).hasSize(1);
    }

    @Test
    void sourceErrorStaysPartialAndDoesNotHideTheOtherSource() {
        Fake his = patientSource("mini-his", "https://lab.local/mini-his", "MHS-PAT-001");
        Fake lis = new Fake("mini-lis");
        lis.failure = ClinicalReadException.unavailable();
        LinkStore store = new LinkStore();
        store.link("mini-his", "https://lab.local/mini-his/patient", "MHS-PAT-001", "mini-lis", "LIS-PAT-1");
        FederationService service = service(store, List.of(his, lis), 20);

        JsonNode body = service.query("mini-his", request(List.of("mini-his", "mini-lis"), List.of("Patient")));

        assertThat(body.path("status").asText()).isEqualTo("partial");
        assertThat(outcome(body, "mini-lis")).isEqualTo("unavailable");
        assertThat(entries(body, "mini-his", "Patient")).hasSize(1);
        assertThat(body.toString()).doesNotContain("Quispe");
    }

    @Test
    void expiredBudgetFailsWithoutCallingConnectors() {
        Fake his = patientSource("mini-his", "https://lab.local/mini-his", "MHS-PAT-001");
        FederationService service = service(new LinkStore(), List.of(his), 0);

        JsonNode body = service.query("mini-his", request(List.of("mini-his"), List.of("Patient")));

        assertThat(body.path("status").asText()).isEqualTo("failed");
        assertThat(outcome(body, "mini-his")).isEqualTo("unavailable");
        assertThat(body.path("sources").get(0).path("error").asText()).isEqualTo("timeout");
        assertThat(body.path("entries")).isEmpty();
        assertThat(his.resolveCalls).isZero();
    }

    @Test
    void reverseLinkDoesNotResolveTheOtherOrganization() {
        LinkStore store = new LinkStore();
        store.link("mini-lis", "https://lab.local/mini-his/patient", "MHS-PAT-001", "mini-his", "MHS-PAT-001");
        Fake his = patientSource("mini-his", "https://lab.local/mini-his", "MHS-PAT-001");
        Fake lis = new Fake("mini-lis");
        FederationService service = service(store, List.of(his, lis), 20);

        JsonNode body = service.query("mini-his", request(List.of("mini-his", "mini-lis"), List.of("Patient")));

        assertThat(outcome(body, "mini-his")).isEqualTo("complete");
        assertThat(outcome(body, "mini-lis")).isEqualTo("identity_unresolved");
        assertThat(body.path("status").asText()).isEqualTo("partial");
        assertThat(lis.resolveCalls).isZero();
        assertThat(lis.collectCalls).isZero();
    }

    @Test
    void foreignIdentifierDoesNotQueryAnotherSource() {
        LinkStore store = new LinkStore();
        store.link("mini-his", "https://lab.local/mini-his/patient", "MHS-PAT-001", "mini-lis", "LIS-PAT-1");
        Fake his = patientSource("mini-his", "https://lab.local/mini-his", "MHS-PAT-001");
        Fake lis = new Fake("mini-lis");
        lis.resources.put("Patient", List.of(patient("mini-lis", "LIS-PAT-1")));
        FederationService service = service(store, List.of(his, lis), 20);
        ObjectNode foreign = request(List.of("mini-his", "mini-lis"), List.of("Patient"));
        foreign.withObject("patient").put("identifierSystem", "https://lab.local/mini-lis/patient");
        foreign.withObject("patient").put("identifierValue", "LIS-PAT-1");

        JsonNode body = service.query("mini-his", foreign);

        assertThat(body.path("status").asText()).isEqualTo("failed");
        assertThat(outcome(body, "mini-his")).isEqualTo("identity_unresolved");
        assertThat(outcome(body, "mini-lis")).isEqualTo("identity_unresolved");
        assertThat(body.path("entries")).isEmpty();
        assertThat(lis.resolveCalls).isZero();
        assertThat(lis.collectCalls).isZero();
        assertThat(body.toString()).doesNotContain("LIS-PAT-1");
    }

    @Test
    void sameLocalIdFromTwoOrganizationsStaysTwoResources() {
        LinkStore store = new LinkStore();
        store.link("mini-his", "https://lab.local/mini-his/patient", "MHS-PAT-001", "mini-lis", "SHARED");
        Fake his = patientSource("mini-his", "https://lab.local/mini-his", "MHS-PAT-001");
        his.resources.put("Observation", List.of(observation("mini-his", "SHARED", "GLU", "141", "mmol/L")));
        Fake lis = new Fake("mini-lis");
        lis.resources.put("Patient", List.of(patient("mini-lis", "SHARED")));
        lis.resources.put("Observation", List.of(observation("mini-lis", "SHARED", "GLU", "141", "mmol/L")));
        FederationService service = service(store, List.of(his, lis), 20);

        JsonNode body = service.query("mini-his", request(List.of("mini-his", "mini-lis"), List.of("Patient", "Observation")));

        assertThat(body.path("status").asText()).isEqualTo("complete");
        assertThat(entries(body, "mini-his", "Observation")).hasSize(1);
        assertThat(entries(body, "mini-lis", "Observation")).hasSize(1);
        assertThat(entries(body, "mini-his", "Observation").get(0).path("fullUrl").asText())
                .isEqualTo("http://mini-his.test/Observation/SHARED");
        assertThat(entries(body, "mini-lis", "Observation").get(0).path("fullUrl").asText())
                .isEqualTo("http://mini-lis.test/Observation/SHARED");
        assertThat(entries(body, "mini-his", "Observation").get(0).path("resource").path("meta").path("source").asText())
                .isEqualTo("https://lab.local/mini-his");
        assertThat(entries(body, "mini-lis", "Observation").get(0).path("resource").path("meta").path("source").asText())
                .isEqualTo("https://lab.local/mini-lis");
    }

    @Test
    void connectorFailureDoesNotCopyTheExceptionIntoTheResponse() {
        Fake his = patientSource("mini-his", "https://lab.local/mini-his", "MHS-PAT-001");
        Fake lis = new Fake("mini-lis");
        lis.failure = new IllegalStateException("leak-marker patient Quispe value 13.4");
        LinkStore store = new LinkStore();
        store.link("mini-his", "https://lab.local/mini-his/patient", "MHS-PAT-001", "mini-lis", "LIS-PAT-1");
        FederationService service = service(store, List.of(his, lis), 20);

        JsonNode body = service.query("mini-his", request(List.of("mini-his", "mini-lis"), List.of("Patient")));

        assertThat(outcome(body, "mini-lis")).isEqualTo("unavailable");
        assertThat(body.path("sources").toString()).contains("source_error").doesNotContain("leak-marker").doesNotContain("Quispe");
        assertThat(body.path("entries").toString()).doesNotContain("leak-marker");
    }

    @Test
    void demographicFieldsAndForeignIdentityAreRejected() {
        FederationService service = service(new LinkStore(), List.of(), 20);
        ObjectNode demographic = request(null, List.of("Patient"));
        demographic.withObject("patient").put("familyName", "Quispe");

        assertThatThrownBy(() -> service.query("mini-his", demographic))
                .isInstanceOf(FederationException.class)
                .extracting("message")
                .isEqualTo("invalid_request");
        ObjectNode foreign = request(List.of("mini-lis"), List.of("Patient"));
        foreign.put("requestingOrganizationId", "org-mini-lis");
        assertThatThrownBy(() -> service.query("mini-lis", foreign))
                .isInstanceOf(FederationException.class)
                .extracting("message")
                .isEqualTo("identity_system_mismatch");
    }

    @Test
    void authorizedAccessIsAuditedOnceAndOperationalFailureIsNotADenial() {
        List<FederationSecurityAuditEvent> events = new ArrayList<>();
        Fake his = patientSource("mini-his", "https://lab.local/mini-his", "MHS-PAT-001");
        Fake lis = patientSource("mini-lis", "https://lab.local/mini-lis", "MLS-PAT-001");
        FederationService service = auditedService(new LinkStore(), List.of(his, lis), 0, events::add);

        JsonNode body = service.query(
                "mini-his", request(List.of("mini-his", "mini-lis"), List.of("Patient")));

        assertThat(body.path("status").asText()).isEqualTo("failed");
        assertThat(outcome(body, "mini-his")).isEqualTo("unavailable");
        assertThat(outcome(body, "mini-lis")).isEqualTo("unavailable");
        assertThat(events).singleElement().satisfies(event -> {
            assertThat(event.outcome()).isEqualTo("allowed");
            assertThat(event.reasonCode()).isEqualTo("access_granted");
            assertThat(event.actorId()).isEqualTo("mini-his");
            assertThat(event.organizationId()).isEqualTo("org-mini-his");
            assertThat(event.correlationId()).isEqualTo("FED-0123456789ABCDEF");
            assertThat(event.metadata()).isEqualTo(Map.of(
                    "route", "/api/clinical-federation/v1/context"));
        });
        assertThat(his.resolveCalls).isZero();
        assertThat(lis.resolveCalls).isZero();
    }

    @Test
    void acceptedLegacyCorrelationIsPreservedOnlyInTheResponse() {
        List<FederationSecurityAuditEvent> events = new ArrayList<>();
        Fake his = patientSource("mini-his", "https://lab.local/mini-his", "MHS-PAT-001");
        FederationService service = auditedService(new LinkStore(), List.of(his), 0, events::add);
        ObjectNode request = request(List.of("mini-his"), List.of("Patient"));
        request.put("correlationId", "FED-UNIT-0001");

        JsonNode body = service.query("mini-his", request);

        assertThat(body.path("correlationId").asText()).isEqualTo("FED-UNIT-0001");
        assertThat(events).singleElement().satisfies(event -> assertThat(event.correlationId())
                .matches("FED-[A-F0-9]{16}")
                .isNotEqualTo("FED-UNIT-0001"));
        assertThat(his.resolveCalls).isZero();
    }

    @Test
    void retryProducesOneIndependentDecisionPerRequest() {
        List<FederationSecurityAuditEvent> events = new ArrayList<>();
        Fake his = patientSource("mini-his", "https://lab.local/mini-his", "MHS-PAT-001");
        FederationService service = auditedService(new LinkStore(), List.of(his), 0, events::add);
        ObjectNode request = request(List.of("mini-his"), List.of("Patient"));

        service.query("mini-his", request);
        service.query("mini-his", request);

        assertThat(events).hasSize(2);
        assertThat(events).extracting(FederationSecurityAuditEvent::eventId).doesNotHaveDuplicates();
        assertThat(events).extracting(FederationSecurityAuditEvent::outcome)
                .containsExactly("allowed", "allowed");
        assertThat(events).extracting(FederationSecurityAuditEvent::correlationId)
                .containsExactly("FED-0123456789ABCDEF", "FED-0123456789ABCDEF");
        assertThat(his.resolveCalls).isZero();
    }

    @Test
    void authorizationDenialsUseVerifiedCallerIdentityAndSpecificReasons() {
        List<FederationSecurityAuditEvent> events = new ArrayList<>();
        Fake his = patientSource("mini-his", "https://lab.local/mini-his", "MHS-PAT-001");
        FederationProperties properties = properties(20);
        properties.getGrants().put("mini-his", List.of("mini-his"));
        FederationService service = new FederationService(
                registry(),
                new LinkStore(),
                List.of(his),
                properties,
                json,
                audit(events::add));

        ObjectNode organization = request(List.of("mini-his"), List.of("Patient"));
        organization.put("requestingOrganizationId", "org-mini-lis");
        assertThatThrownBy(() -> service.query("mini-his", organization))
                .isInstanceOf(FederationException.class)
                .extracting("message")
                .isEqualTo("organization_mismatch");

        ObjectNode callerSystem = request(List.of("mini-his"), List.of("Patient"));
        callerSystem.withObject("patient").put("systemKey", "mini-lis");
        assertThatThrownBy(() -> service.query("mini-his", callerSystem))
                .isInstanceOf(FederationException.class)
                .extracting("message")
                .isEqualTo("identity_system_mismatch");

        assertThatThrownBy(() -> service.query(
                        "mini-his", request(List.of("mini-his", "mini-lis"), List.of("Patient"))))
                .isInstanceOf(FederationException.class)
                .extracting("message")
                .isEqualTo("source_not_authorized");

        assertThat(events).extracting(FederationSecurityAuditEvent::reasonCode)
                .containsExactly(
                        "organization_not_authorized",
                        "caller_system_not_authorized",
                        "source_not_granted");
        assertThat(events).allSatisfy(event -> {
            assertThat(event.outcome()).isEqualTo("denied");
            assertThat(event.actorId()).isEqualTo("mini-his");
            assertThat(event.organizationId()).isEqualTo("org-mini-his");
        });
        assertThat(his.resolveCalls).isZero();
    }

    @Test
    void missingServerAuthenticatedCallerIsAuditedAsAnonymous() {
        List<FederationSecurityAuditEvent> events = new ArrayList<>();
        FederationService service = auditedService(new LinkStore(), List.of(), 20, events::add);

        assertThatThrownBy(() -> service.query(null, request(List.of("mini-his"), List.of("Patient"))))
                .isInstanceOf(FederationException.class)
                .extracting("message")
                .isEqualTo("unauthenticated");

        assertThat(events).singleElement().satisfies(event -> {
            assertThat(event.outcome()).isEqualTo("denied");
            assertThat(event.reasonCode()).isEqualTo("participant_not_authenticated");
            assertThat(event.actorType()).isEqualTo("anonymous");
            assertThat(event.organizationId()).isNull();
        });
    }

    @Test
    void authenticatedButUnregisteredParticipantHasNoVerifiedOrganization() {
        List<FederationSecurityAuditEvent> events = new ArrayList<>();
        FederationService service = auditedService(new LinkStore(), List.of(), 20, events::add);

        assertThatThrownBy(() -> service.query(
                        "unknown-participant", request(List.of("mini-his"), List.of("Patient"))))
                .isInstanceOf(FederationException.class)
                .extracting("message")
                .isEqualTo("unauthenticated");

        assertThat(events).singleElement().satisfies(event -> {
            assertThat(event.outcome()).isEqualTo("denied");
            assertThat(event.reasonCode()).isEqualTo("participant_not_registered");
            assertThat(event.actorId()).isEqualTo("unknown-participant");
            assertThat(event.organizationId()).isNull();
        });
    }

    @Test
    void controllerPreservesAuthorizationAndAuditUnavailableResponses() {
        FederationController controller = new FederationController(null);

        var forbidden = controller.failed(FederationException.forbidden("source_not_authorized"));
        var unavailable = controller.failed(FederationException.unavailable("audit_unavailable"));

        assertThat(forbidden.getStatusCode().value()).isEqualTo(403);
        assertThat(forbidden.getBody()).isEqualTo(Map.of("error", "source_not_authorized"));
        assertThat(unavailable.getStatusCode().value()).isEqualTo(503);
        assertThat(unavailable.getBody()).isEqualTo(Map.of("error", "audit_unavailable"));
    }

    @Test
    void invalidSourceSyntaxIsValidationFailureAndNotAnAccessDenial() {
        List<FederationSecurityAuditEvent> events = new ArrayList<>();
        Fake his = patientSource("mini-his", "https://lab.local/mini-his", "MHS-PAT-001");
        FederationService service = auditedService(new LinkStore(), List.of(his), 20, events::add);

        assertThatThrownBy(() -> service.query(
                        "mini-his", request(List.of("outside-grant", "../../patient"), List.of("Patient"))))
                .isInstanceOf(FederationException.class)
                .extracting("message")
                .isEqualTo("invalid_request");

        assertThat(events).isEmpty();
        assertThat(his.resolveCalls).isZero();
    }

    @Test
    void auditFailureIs503AndPreventsEveryConnectorCall() {
        Fake his = patientSource("mini-his", "https://lab.local/mini-his", "MHS-PAT-001");
        FederationService service = auditedService(
                new LinkStore(),
                List.of(his),
                20,
                event -> {
                    throw new FederationSecurityAuditUnavailable();
                });

        assertThatThrownBy(() -> service.query(
                        "mini-his", request(List.of("mini-his"), List.of("Patient"))))
                .isInstanceOfSatisfying(FederationException.class, ex -> {
                    assertThat(ex.code()).isEqualTo("audit_unavailable");
                    assertThat(ex.httpStatus()).isEqualTo(503);
                });
        assertThat(his.resolveCalls).isZero();
        assertThat(his.collectCalls).isZero();
    }

    private FederationService service(LinkStore store, List<ClinicalConnector> connectors, int budgetSeconds) {
        return auditedService(store, connectors, budgetSeconds, event -> {});
    }

    private FederationService auditedService(
            LinkStore store,
            List<ClinicalConnector> connectors,
            int budgetSeconds,
            lab.healthcare.fhir.federation.audit.FederationSecurityAuditRecorder recorder) {
        return new FederationService(
                registry(),
                store,
                connectors,
                properties(budgetSeconds),
                json,
                audit(recorder));
    }

    private FederationSecurityAudit audit(
            lab.healthcare.fhir.federation.audit.FederationSecurityAuditRecorder recorder) {
        return new FederationSecurityAudit(
                recorder,
                Clock.fixed(Instant.parse("2026-10-23T12:00:00Z"), ZoneOffset.UTC));
    }

    private FederationProperties properties(int budgetSeconds) {
        FederationProperties properties = new FederationProperties();
        properties.setMaxSources(4);
        properties.setMaxEntries(100);
        properties.setQueryBudgetSeconds(budgetSeconds);
        properties.getGrants().put("mini-his", List.of("mini-his", "mini-lis", "clinic-b"));
        properties.getGrants().put("mini-lis", List.of("mini-lis"));
        return properties;
    }

    private SourceRegistry registry() {
        InteropSourcesProperties properties = new InteropSourcesProperties();
        properties.getSources().put("mini-his", source("org-mini-his", "http://mini-his.test", List.of("patient", "observation")));
        properties.getSources().put("mini-lis", source("org-mini-lis", "http://mini-lis.test", List.of("patient", "observation")));
        properties.getSources().put("clinic-b", source("org-clinic-b", "http://clinic-b.test", List.of("patient")));
        return new SourceRegistry(properties);
    }

    private static InteropSourcesProperties.SourceProperties source(String organizationId, String baseUrl, List<String> capabilities) {
        InteropSourcesProperties.SourceProperties source = new InteropSourcesProperties.SourceProperties();
        source.setOrganizationId(organizationId);
        source.setDisplayName(organizationId);
        source.setBaseUrl(baseUrl);
        source.setCapabilities(capabilities);
        return source;
    }

    private ObjectNode request(List<String> sources, List<String> types) {
        ObjectNode body = json.createObjectNode();
        body.put("requestingOrganizationId", "org-mini-his");
        body.put("correlationId", "FED-0123456789ABCDEF");
        ObjectNode patient = body.putObject("patient");
        patient.put("systemKey", "mini-his");
        patient.put("identifierSystem", "https://lab.local/mini-his/patient");
        patient.put("identifierValue", sources == null ? "MHS-PAT-001" : "MHS-PAT-001");
        if (sources != null) {
            var array = body.putArray("sources");
            sources.forEach(array::add);
        }
        var resourceTypes = body.putArray("resourceTypes");
        types.forEach(resourceTypes::add);
        return body;
    }

    private Fake patientSource(String key, String metaSource, String patientId) {
        Fake source = new Fake(key);
        source.patients.put("https://lab.local/mini-his/patient\n" + patientId, patientId);
        source.resources.put("Patient", List.of(patient(key, patientId, metaSource)));
        return source;
    }

    private ObjectNode patient(String key, String id) {
        return patient(key, id, "https://lab.local/" + key);
    }

    private ObjectNode patient(String key, String id, String metaSource) {
        ObjectNode resource = json.createObjectNode();
        resource.put("resourceType", "Patient");
        resource.put("id", id);
        resource.putObject("meta").put("source", metaSource);
        ObjectNode identifier = resource.putArray("identifier").addObject();
        identifier.put("system", "https://lab.local/" + key + "/patient");
        identifier.put("value", id);
        return resource;
    }

    private ObjectNode observation(String key, String id, String code, String value, String unit) {
        ObjectNode resource = json.createObjectNode();
        resource.put("resourceType", "Observation");
        resource.put("id", id);
        resource.put("status", "final");
        resource.putObject("meta").put("source", "https://lab.local/" + key);
        ObjectNode identifier = resource.putArray("identifier").addObject();
        identifier.put("system", "https://lab.local/" + key + "/result");
        identifier.put("value", id);
        resource.putObject("subject").put("reference", "Patient/MHS-PAT-001");
        ObjectNode coding = resource.putObject("code").putArray("coding").addObject();
        coding.put("system", "https://lab.local/" + key + "/test");
        coding.put("code", code);
        ObjectNode quantity = resource.putObject("valueQuantity");
        quantity.put("value", value);
        quantity.put("unit", unit);
        return resource;
    }

    private static List<JsonNode> entries(JsonNode body, String source, String type) {
        List<JsonNode> found = new ArrayList<>();
        body.path("entries").forEach(entry -> {
            if (source.equals(entry.path("sourceKey").asText())
                    && type.equals(entry.path("resource").path("resourceType").asText())) {
                found.add(entry);
            }
        });
        return found;
    }

    private static String outcome(JsonNode body, String source) {
        for (JsonNode item : body.path("sources")) {
            if (source.equals(item.path("sourceKey").asText())) {
                return item.path("outcome").asText();
            }
        }
        return "";
    }

    private static int count(JsonNode body, String source) {
        for (JsonNode item : body.path("sources")) {
            if (source.equals(item.path("sourceKey").asText())) {
                return item.path("resourceCount").asInt();
            }
        }
        return -1;
    }

    private static final class Fake implements ClinicalConnector {
        private final String key;
        private final Map<String, String> patients = new LinkedHashMap<>();
        private final Map<String, List<JsonNode>> resources = new LinkedHashMap<>();
        private int resolveCalls;
        private int collectCalls;
        private RuntimeException failure;

        private Fake(String key) {
            this.key = key;
        }

        @Override
        public String key() {
            return key;
        }

        @Override
        public String resolvePatient(String identifierSystem, String identifierValue) {
            resolveCalls++;
            if (failure != null) {
                throw failure;
            }
            return patients.get(identifierSystem + "\n" + identifierValue);
        }

        @Override
        public Collected collect(String resourceType, String patientId) {
            collectCalls++;
            if (failure != null) {
                throw failure;
            }
            return new Collected(resources.getOrDefault(resourceType, List.of()), false);
        }
    }

    private static final class LinkStore implements ExchangeStore {
        private final Map<String, String> links = new LinkedHashMap<>();

        private void link(String source, String system, String value, String destination, String patientId) {
            links.put(source + "\n" + system + "\n" + value + "\n" + destination, patientId);
        }

        @Override
        public Optional<String> findPatientLink(String sourceSystem, String identifierSystem, String identifierValue, String destinationSystem) {
            return Optional.ofNullable(links.get(sourceSystem + "\n" + identifierSystem + "\n" + identifierValue + "\n" + destinationSystem));
        }

        @Override
        public void savePatientLink(String sourceSystem, String identifierSystem, String identifierValue, String destinationSystem, String destinationPatientId) {
            throw new UnsupportedOperationException();
        }

        @Override
        public Optional<OrderCorrelation> findOrder(String sourceSystem, String sourceOrganizationId, String sourceOrderId, String destinationSystem) {
            throw new UnsupportedOperationException();
        }

        @Override
        public Optional<OrderCorrelation> findOwnedOrder(String sourceSystem, String sourceOrderId) {
            throw new UnsupportedOperationException();
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
            throw new UnsupportedOperationException();
        }

        @Override
        public boolean saveHl7Observation(String messageControlId, String destinationOrderId, String sourceOrderId, String externalResultId, String observationJson) {
            throw new UnsupportedOperationException();
        }

        @Override
        public List<String> hl7Observations(String destinationOrderId) {
            throw new UnsupportedOperationException();
        }
    }
}

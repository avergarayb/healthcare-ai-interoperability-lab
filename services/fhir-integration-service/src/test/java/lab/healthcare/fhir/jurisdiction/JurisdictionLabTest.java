package lab.healthcare.fhir.jurisdiction;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import lab.healthcare.fhir.exchange.ExchangeStore;
import lab.healthcare.fhir.exchange.OrderCorrelation;
import lab.healthcare.fhir.federation.ClinicalConnector;
import lab.healthcare.fhir.federation.FederationException;
import lab.healthcare.fhir.federation.FederationProperties;
import lab.healthcare.fhir.federation.FederationService;
import lab.healthcare.fhir.federation.JurisdictionBinding;
import lab.healthcare.fhir.federation.audit.FederationSecurityAudit;
import lab.healthcare.fhir.interop.InteropSourcesProperties;
import lab.healthcare.fhir.interop.SourceRegistry;
import org.junit.jupiter.api.Test;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class JurisdictionLabTest {

    private final ObjectMapper json = new ObjectMapper();

    @Test
    void peruAndSpainStaySeparateInsideOneFederation() {
        JurisdictionProfile peru = JurisdictionProfile.require("pe-lab-demo-v1");
        JurisdictionProfile spain = JurisdictionProfile.require("es-lab-demo-v1");
        FederationService service = service(peru, spain);

        ObjectNode peruvian = (ObjectNode) service.query("mini-his", request(peru, List.of(peru.sourceKey())));
        assertThat(peruvian.path("status").asText()).isEqualTo("complete");
        assertThat(peruvian.path("truncated").asBoolean()).isFalse();
        assertThat(peruvian.path("sources")).hasSize(1);
        assertThat(peruvian.path("entries").toString()).contains("718-7").contains("internal-demo-rules");
        assertThat(peruvian.path("entries").toString())
                .contains("pe-obs-718-7")
                .contains("pe-long-718-7-20261001")
                .contains("2026-10-01T08:00:00Z")
                .contains("12.8")
                .contains("pe-long-718-7-20261115")
                .contains("2026-11-15T08:00:00Z")
                .contains("longitudinal-series");
        assertThat(peruvian.path("entries").toString()).doesNotContain("gob.pe/minsa");

        ObjectNode spanish = (ObjectNode) service.query("mini-his", request(spain, List.of(spain.sourceKey())));
        assertThat(spanish.path("status").asText()).isEqualTo("complete");
        assertThat(spanish.path("entries").toString()).contains("2345-7").contains("es-lab-demo-v1");
        assertThat(spanish.path("entries").toString())
                .contains("es-obs-2345-7")
                .contains("es-long-2345-7-20261001")
                .contains("95")
                .contains("es-long-2345-7-20261115")
                .contains("longitudinal-series");
        assertThat(spanish.path("entries").toString()).doesNotContain("PE-PAT-001");

        assertThatThrownBy(() -> service.query("mini-his", request(peru, List.of(peru.sourceKey(), spain.sourceKey()))))
                .isInstanceOfSatisfying(FederationException.class, error -> {
                    assertThat(error.code()).isEqualTo("cross_border_denied");
                    assertThat(error.httpStatus()).isEqualTo(403);
                });
    }

    @Test
    void closedProfilesRejectUnknownVersionsAndOfficialClaims() {
        assertThatThrownBy(() -> JurisdictionProfile.require(" ")).isInstanceOf(IllegalStateException.class)
                .hasMessage("profile_unknown");
        assertThatThrownBy(() -> JurisdictionProfile.require("pe-lab-demo-v9")).isInstanceOf(IllegalStateException.class)
                .hasMessage("profile_version_unavailable");
        JurisdictionProfile peru = JurisdictionProfile.require("pe-lab-demo-v1");
        ObjectNode observation = peru.resources(json).get(1);
        observation.putObject("meta").putArray("profile").add(
                "https://www.gob.pe/minsa/RENHICE/fhir/StructureDefinition/Patient");
        assertThat(JurisdictionLabValidator.validate(peru, observation)).isEqualTo("profile_not_verified");
        ObjectNode foreign = peru.resources(json).get(1).deepCopy();
        foreign.withObject("subject").put("reference", "Patient/es-pat-001");
        assertThat(JurisdictionLabValidator.validate(peru, foreign)).isEqualTo("context_rejected");
        ObjectNode unit = peru.resources(json).get(1).deepCopy();
        unit.withObject("valueQuantity").put("system", "http://example.org").put("unit", "mmol/L");
        assertThat(JurisdictionLabValidator.validate(peru, unit)).isEqualTo("context_rejected");
        ObjectNode incomplete = peru.resources(json).get(1).deepCopy();
        incomplete.remove("valueQuantity");
        assertThat(JurisdictionLabValidator.validate(peru, incomplete)).isEqualTo("context_incomplete");
        ObjectNode broken = json.createObjectNode();
        assertThat(JurisdictionLabValidator.validate(peru, broken)).isEqualTo("response_rejected");
    }

    @Test
    void callerOrganizationAndIdentifierStayClosed() {
        JurisdictionProfile peru = JurisdictionProfile.require("pe-lab-demo-v1");
        FederationService service = service(peru, JurisdictionProfile.require("es-lab-demo-v1"));
        ObjectNode wrongOrganization = request(peru, List.of(peru.sourceKey()));
        wrongOrganization.put("requestingOrganizationId", "org-es-lab-demo");
        assertThatThrownBy(() -> service.query("mini-his", wrongOrganization))
                .isInstanceOfSatisfying(FederationException.class, error ->
                        assertThat(error.code()).isEqualTo("organization_mismatch"));
        ObjectNode wrongPatient = request(peru, List.of(peru.sourceKey()));
        wrongPatient.withObject("patient").put("identifierValue", "ES-PAT-001");
        ObjectNode unresolved = (ObjectNode) service.query("mini-his", wrongPatient);
        assertThat(unresolved.path("sources").get(0).path("outcome").asText()).isEqualTo("identity_unresolved");
    }

    private FederationService service(JurisdictionProfile peru, JurisdictionProfile spain) {
        InteropSourcesProperties sources = new InteropSourcesProperties();
        InteropSourcesProperties.SourceProperties local = new InteropSourcesProperties.SourceProperties();
        local.setOrganizationId("org-mini-his");
        local.setDisplayName("Mini HIS");
        local.setBaseUrl("http://127.0.0.1:8095");
        local.setCapabilities(List.of("patient", "observation"));
        sources.getSources().put("mini-his", local);
        SourceRegistry registry = new SourceRegistry(sources)
                .withAdditional(peru.descriptor())
                .withAdditional(spain.descriptor());
        FederationProperties properties = new FederationProperties();
        properties.setMaxSources(4);
        properties.setMaxEntries(100);
        properties.setQueryBudgetSeconds(20);
        properties.getGrants().put("mini-his", List.of("mini-his", peru.sourceKey(), spain.sourceKey()));
        List<ClinicalConnector> connectors = List.of(new JurisdictionLabConnector(peru), new JurisdictionLabConnector(spain));
        Map<String, JurisdictionBinding> bindings = Map.of(
                peru.sourceKey(), peru.binding(),
                spain.sourceKey(), spain.binding());
        return new FederationService(
                registry, new UnusedExchange(), connectors, properties, json,
                new FederationSecurityAudit(event -> {}, Clock.fixed(Instant.parse("2026-11-17T12:00:00Z"), ZoneOffset.UTC)),
                null, Set.of(peru.sourceKey(), spain.sourceKey()), bindings);
    }

    private ObjectNode request(JurisdictionProfile profile, List<String> sources) {
        ObjectNode body = json.createObjectNode();
        body.put("requestingOrganizationId", "org-mini-his");
        body.put("correlationId", "FED-0123456789ABCDEF");
        ObjectNode patient = body.putObject("patient");
        patient.put("systemKey", "mini-his");
        patient.put("identifierSystem", profile.patientSystem());
        patient.put("identifierValue", profile.patientValue());
        var selected = body.putArray("sources");
        sources.forEach(selected::add);
        body.putArray("resourceTypes").add("Patient").add("Observation");
        return body;
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
        public java.util.List<String> hl7Observations(String destinationOrderId) {
            return List.of();
        }
    }
}

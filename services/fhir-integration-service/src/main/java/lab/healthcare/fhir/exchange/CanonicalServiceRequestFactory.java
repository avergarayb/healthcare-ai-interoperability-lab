package lab.healthcare.fhir.exchange;

import lab.healthcare.fhir.interop.SourceRegistry.SourceDescriptor;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;

import java.time.OffsetDateTime;
import java.time.ZoneOffset;

/**
 * Builds the canonical FHIR R4 ServiceRequest. Test codes stay in a laboratory
 * system derived from the source key. This class does not emit LOINC or UCUM.
 */
final class CanonicalServiceRequestFactory {

    static final String META_SOURCE = "https://lab.local/exchange";
    static final String CORRELATION_SYSTEM = "https://lab.local/exchange/service-request";
    static final String ORGANIZATION_SYSTEM = "https://lab.local/exchange/organization";
    static final String DESTINATION_ORDER_SYSTEM = "https://lab.local/exchange/destination-order";

    private final ObjectMapper json;

    CanonicalServiceRequestFactory(ObjectMapper json) {
        this.json = json;
    }

    ObjectNode create(OrderCorrelation correlation, SourceDescriptor source, SourceDescriptor destination) {
        ObjectNode resource = json.createObjectNode();
        resource.put("resourceType", "ServiceRequest");
        resource.put("id", correlation.sourceOrderId());
        resource.putObject("meta").put("source", META_SOURCE);
        var identifiers = resource.putArray("identifier");
        identifiers.addObject().put("system", CORRELATION_SYSTEM).put("value", correlation.correlationId());
        identifiers.addObject()
                .put("system", sourceOrderSystem(correlation.sourceOrganizationId()))
                .put("value", correlation.sourceOrderId());
        if (correlation.destinationOrderId() != null) {
            identifiers.addObject()
                    .put("system", DESTINATION_ORDER_SYSTEM)
                    .put("value", correlation.destinationOrderId());
        }
        resource.put("status", "active");
        resource.put("intent", "order");
        resource.putObject("subject")
                .putObject("identifier")
                .put("system", correlation.patientIdentifierSystem())
                .put("value", correlation.patientIdentifierValue());
        ObjectNode coding = resource.putObject("code").putArray("coding").addObject();
        coding.put("system", testSystem(source.key()));
        coding.put("code", correlation.testCode());
        resource.with("code").put("text", correlation.testDescription());
        resource.put("authoredOn", correlation.requestedAt().withOffsetSameInstant(ZoneOffset.UTC).toString());
        resource.putObject("requester")
                .putObject("identifier")
                .put("system", ORGANIZATION_SYSTEM)
                .put("value", source.organizationId());
        resource.putArray("performer")
                .addObject()
                .putObject("identifier")
                .put("system", ORGANIZATION_SYSTEM)
                .put("value", destination.organizationId());
        return resource;
    }

    static String testSystem(String sourceSystem) {
        return "https://lab.local/" + sourceSystem + "/test";
    }

    static String sourceOrderSystem(String sourceOrganizationId) {
        return "https://lab.local/" + sourceOrganizationId + "/service-request";
    }

    DestinationCommand command(ObjectNode serviceRequest, String destinationPatientId) {
        String system = serviceRequest.path("code").path("coding").path(0).path("system").asText("");
        if (system.toLowerCase().contains("loinc") || serviceRequest.toString().toLowerCase().contains("ucum")) {
            throw ExchangeException.invalidRequest();
        }
        String code = serviceRequest.path("code").path("coding").path(0).path("code").asText("");
        String text = serviceRequest.path("code").path("text").asText("");
        String requester = serviceRequest.path("requester").path("identifier").path("value").asText("");
        String performer = serviceRequest.path("performer").path(0).path("identifier").path("value").asText("");
        String externalRequestId = identifier(serviceRequest, sourceOrderSystem(requester));
        String authored = serviceRequest.path("authoredOn").asText("");
        if (destinationPatientId.isBlank() || code.isBlank() || text.isBlank()
                || requester.isBlank() || performer.isBlank() || externalRequestId == null || authored.isBlank()) {
            throw ExchangeException.invalidRequest();
        }
        OffsetDateTime requestedAt;
        try {
            requestedAt = OffsetDateTime.parse(authored);
        } catch (RuntimeException ex) {
            throw ExchangeException.invalidRequest();
        }
        return new DestinationCommand(
                destinationPatientId,
                requester,
                externalRequestId,
                code,
                text,
                requestedAt,
                performer,
                system);
    }

    private static String identifier(ObjectNode resource, String system) {
        var identifiers = resource.path("identifier");
        if (!identifiers.isArray()) {
            return null;
        }
        for (var identifier : identifiers) {
            if (system.equals(identifier.path("system").asText())) {
                String value = identifier.path("value").asText("");
                return value.isBlank() ? null : value;
            }
        }
        return null;
    }
}

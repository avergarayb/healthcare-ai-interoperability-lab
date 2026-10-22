package lab.healthcare.fhir.exchange;

import com.fasterxml.jackson.databind.JsonNode;

import java.util.List;

public record ExchangeReceipt(
        String correlationId,
        String deliveryState,
        ExchangeParty source,
        ExchangeParty destination,
        JsonNode serviceRequest,
        JsonNode destinationServiceRequest,
        JsonNode diagnosticReport,
        List<JsonNode> observations) {
}

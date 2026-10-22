package lab.healthcare.fhir.exchange;

import com.fasterxml.jackson.databind.JsonNode;

import java.util.List;

public interface ResultSource {

    String systemKey();

    DestinationReport read(String destinationOrderId);
}

record DestinationReport(JsonNode serviceRequest, JsonNode diagnosticReport, List<JsonNode> observations) {
}

package lab.healthcare.fhir.exchange;

public record AcceptedOrder(String orderId, boolean alreadyPresent) {
}

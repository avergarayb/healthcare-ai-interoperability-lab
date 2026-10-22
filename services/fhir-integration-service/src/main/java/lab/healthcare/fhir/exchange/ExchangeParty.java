package lab.healthcare.fhir.exchange;

public record ExchangeParty(String systemKey, String organizationId, String orderId, String patientId) {
}

package lab.healthcare.fhir.exchange;

public record AcceptedOrder(String orderId, boolean alreadyPresent, String patientId) {

    public AcceptedOrder(String orderId, boolean alreadyPresent) {
        this(orderId, alreadyPresent, null);
    }
}

package lab.healthcare.fhir.exchange;

import java.util.Optional;

public interface ExchangeStore {

    Optional<String> findPatientLink(
            String sourceSystem,
            String identifierSystem,
            String identifierValue,
            String destinationSystem);

    void savePatientLink(
            String sourceSystem,
            String identifierSystem,
            String identifierValue,
            String destinationSystem,
            String destinationPatientId);

    Optional<OrderCorrelation> findOrder(
            String sourceSystem,
            String sourceOrganizationId,
            String sourceOrderId,
            String destinationSystem);

    Optional<OrderCorrelation> findOwnedOrder(String sourceSystem, String sourceOrderId);

    void insert(OrderCorrelation correlation);

    void updateDelivery(
            String correlationId,
            String deliveryState,
            String errorCode,
            String destinationOrderId,
            String destinationPatientId);

    Optional<OrderCorrelation> findByDestinationOrder(String destinationSystem, String destinationOrderId);

    boolean saveHl7Observation(
            String messageControlId,
            String destinationOrderId,
            String sourceOrderId,
            String externalResultId,
            String observationJson);

    java.util.List<String> hl7Observations(String destinationOrderId);
}

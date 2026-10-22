package lab.healthcare.fhir.exchange;

/**
 * Outbound connector for one registered system. Routing selects it by system key.
 */
public interface OrderDestination {

    String systemKey();

    /**
     * Finds or creates the destination patient by requesting organization and
     * external identifier. Implementations must not search by name.
     */
    String resolvePatient(String requestingOrganizationId, PatientIdentity identity);

    AcceptedOrder accept(DestinationCommand command);
}

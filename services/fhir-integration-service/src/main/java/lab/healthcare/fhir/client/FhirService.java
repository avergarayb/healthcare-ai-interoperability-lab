package lab.healthcare.fhir.client;

import ca.uhn.fhir.rest.client.api.IGenericClient;
import ca.uhn.fhir.rest.client.exceptions.FhirClientConnectionException;
import ca.uhn.fhir.rest.server.exceptions.BaseServerResponseException;
import org.hl7.fhir.r4.model.Bundle;
import org.hl7.fhir.r4.model.CapabilityStatement;
import org.hl7.fhir.r4.model.Patient;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.function.Supplier;

@Service
public class FhirService {

    private final IGenericClient fhirClient;

    public FhirService(IGenericClient fhirClient) {
        this.fhirClient = fhirClient;
    }

    public CapabilityStatement retrieveCapabilityStatement() {
        return execute(
                () -> fhirClient.capabilities()
                        .ofType(CapabilityStatement.class)
                        .execute(),
                "retrieving metadata");
    }

    public Patient readPatient(String logicalId) {
        requireText(logicalId, "Patient logical ID must be provided");
        return execute(
                () -> fhirClient.read()
                        .resource(Patient.class)
                        .withId(logicalId)
                        .execute(),
                "reading Patient/" + logicalId);
    }

    public Bundle searchPatientsByName(String name) {
        requireText(name, "Patient name search parameter must be provided");
        return execute(
                () -> fhirClient.search()
                        .forResource(Patient.class)
                        .where(Patient.NAME.matches().value(name))
                        .returnBundle(Bundle.class)
                        .execute(),
                "searching Patient by name");
    }

    public Bundle searchPatientsByIdentifier(String identifier) {
        requireText(identifier, "Patient identifier search parameter must be provided");
        return execute(
                () -> fhirClient.search()
                        .forResource(Patient.class)
                        .where(Patient.IDENTIFIER.exactly().identifier(identifier))
                        .returnBundle(Bundle.class)
                        .execute(),
                "searching Patient by identifier");
    }

    public List<Patient> extractPatients(Bundle bundle) {
        if (bundle == null) {
            throw new IllegalArgumentException("Bundle must be provided");
        }
        return bundle.getEntry().stream()
                .map(Bundle.BundleEntryComponent::getResource)
                .filter(Patient.class::isInstance)
                .map(Patient.class::cast)
                .toList();
    }

    private <T> T execute(Supplier<T> operation, String action) {
        try {
            return operation.get();
        } catch (FhirClientConnectionException ex) {
            throw new FhirClientException("Unable to connect to the FHIR server while " + action, ex);
        } catch (BaseServerResponseException ex) {
            throw new FhirClientException("FHIR server returned an error while " + action, ex);
        }
    }

    private static void requireText(String value, String message) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(message);
        }
    }
}

package lab.healthcare.fhir.client;

import ca.uhn.fhir.rest.client.api.IGenericClient;
import ca.uhn.fhir.rest.client.exceptions.FhirClientConnectionException;
import ca.uhn.fhir.rest.server.exceptions.BaseServerResponseException;
import org.hl7.fhir.r4.model.CapabilityStatement;
import org.springframework.stereotype.Service;

@Service
public class FhirService {

    private final IGenericClient fhirClient;

    public FhirService(IGenericClient fhirClient) {
        this.fhirClient = fhirClient;
    }

    public CapabilityStatement retrieveCapabilityStatement() {
        try {
            return fhirClient.capabilities()
                    .ofType(CapabilityStatement.class)
                    .execute();
        } catch (FhirClientConnectionException ex) {
            throw new FhirClientException("Unable to connect to the FHIR server while retrieving metadata", ex);
        } catch (BaseServerResponseException ex) {
            throw new FhirClientException("FHIR server returned an error while retrieving metadata", ex);
        }
    }
}

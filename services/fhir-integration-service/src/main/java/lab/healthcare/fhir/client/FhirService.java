package lab.healthcare.fhir.client;

import ca.uhn.fhir.rest.client.api.IGenericClient;
import ca.uhn.fhir.rest.client.exceptions.FhirClientConnectionException;
import ca.uhn.fhir.rest.server.exceptions.BaseServerResponseException;
import org.hl7.fhir.r4.model.Bundle;
import org.hl7.fhir.r4.model.CapabilityStatement;
import org.hl7.fhir.r4.model.Condition;
import org.hl7.fhir.r4.model.Observation;
import org.hl7.fhir.r4.model.Patient;
import org.hl7.fhir.r4.model.Reference;
import org.hl7.fhir.r4.model.Resource;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Objects;
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
        return extractResources(bundle, Patient.class);
    }

    public Observation readObservation(String logicalId) {
        requireText(logicalId, "Observation logical ID must be provided");
        return execute(
                () -> fhirClient.read()
                        .resource(Observation.class)
                        .withId(logicalId)
                        .execute(),
                "reading Observation/" + logicalId);
    }

    public Condition readCondition(String logicalId) {
        requireText(logicalId, "Condition logical ID must be provided");
        return execute(
                () -> fhirClient.read()
                        .resource(Condition.class)
                        .withId(logicalId)
                        .execute(),
                "reading Condition/" + logicalId);
    }

    public Bundle searchObservationsByPatient(String patientLogicalId) {
        requireText(patientLogicalId, "Patient logical ID must be provided");
        return execute(
                () -> fhirClient.search()
                        .forResource(Observation.class)
                        .where(Observation.PATIENT.hasId(patientLogicalId))
                        .returnBundle(Bundle.class)
                        .execute(),
                "searching Observation by patient");
    }

    public Bundle searchConditionsByPatient(String patientLogicalId) {
        requireText(patientLogicalId, "Patient logical ID must be provided");
        return execute(
                () -> fhirClient.search()
                        .forResource(Condition.class)
                        .where(Condition.PATIENT.hasId(patientLogicalId))
                        .returnBundle(Bundle.class)
                        .execute(),
                "searching Condition by patient");
    }

    public List<Observation> extractObservations(Bundle bundle) {
        return extractResources(bundle, Observation.class);
    }

    public List<Condition> extractConditions(Bundle bundle) {
        return extractResources(bundle, Condition.class);
    }

    public Bundle searchObservationsByPatientIncludingSubject(String patientLogicalId) {
        requireText(patientLogicalId, "Patient logical ID must be provided");
        return execute(
                () -> fhirClient.search()
                        .forResource(Observation.class)
                        .where(Observation.PATIENT.hasId(patientLogicalId))
                        .include(Observation.INCLUDE_SUBJECT)
                        .returnBundle(Bundle.class)
                        .execute(),
                "searching Observation by patient with _include=Observation:subject");
    }

    public Bundle searchPatientRevincludingObservationSubject(String patientLogicalId) {
        requireText(patientLogicalId, "Patient logical ID must be provided");
        return execute(
                () -> fhirClient.search()
                        .forResource(Patient.class)
                        .where(Patient.RES_ID.exactly().code(patientLogicalId))
                        .revInclude(Observation.INCLUDE_SUBJECT)
                        .returnBundle(Bundle.class)
                        .execute(),
                "searching Patient with _revinclude=Observation:subject");
    }

    public Bundle searchPatientRevincludingConditionSubject(String patientLogicalId) {
        requireText(patientLogicalId, "Patient logical ID must be provided");
        return execute(
                () -> fhirClient.search()
                        .forResource(Patient.class)
                        .where(Patient.RES_ID.exactly().code(patientLogicalId))
                        .revInclude(Condition.INCLUDE_SUBJECT)
                        .returnBundle(Bundle.class)
                        .execute(),
                "searching Patient with _revinclude=Condition:subject");
    }

    public Bundle searchPatientRevincludingObservationAndConditionSubject(String patientLogicalId) {
        requireText(patientLogicalId, "Patient logical ID must be provided");
        return execute(
                () -> fhirClient.search()
                        .forResource(Patient.class)
                        .where(Patient.RES_ID.exactly().code(patientLogicalId))
                        .revInclude(Observation.INCLUDE_SUBJECT)
                        .revInclude(Condition.INCLUDE_SUBJECT)
                        .returnBundle(Bundle.class)
                        .execute(),
                "searching Patient with _revinclude Observation:subject and Condition:subject");
    }

    public List<String> resourceIdentities(Bundle bundle) {
        if (bundle == null) {
            throw new IllegalArgumentException("Bundle must be provided");
        }
        return bundle.getEntry().stream()
                .map(Bundle.BundleEntryComponent::getResource)
                .filter(Objects::nonNull)
                .map(resource -> resource.getResourceType().name() + "/" + resource.getIdElement().getIdPart())
                .toList();
    }

    public String subjectReference(Reference subject) {
        if (subject == null || !subject.hasReference()) {
            throw new IllegalArgumentException("Subject reference must be provided");
        }
        return subject.getReference();
    }

    private <T extends Resource> List<T> extractResources(Bundle bundle, Class<T> type) {
        if (bundle == null) {
            throw new IllegalArgumentException("Bundle must be provided");
        }
        return bundle.getEntry().stream()
                .map(Bundle.BundleEntryComponent::getResource)
                .filter(type::isInstance)
                .map(type::cast)
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

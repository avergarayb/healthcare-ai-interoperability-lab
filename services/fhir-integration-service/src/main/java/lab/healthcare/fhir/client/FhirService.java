package lab.healthcare.fhir.client;

import ca.uhn.fhir.model.api.IQueryParameterType;
import ca.uhn.fhir.rest.api.MethodOutcome;
import ca.uhn.fhir.rest.client.api.IGenericClient;
import ca.uhn.fhir.rest.client.exceptions.FhirClientConnectionException;
import ca.uhn.fhir.rest.param.HasParam;
import ca.uhn.fhir.rest.server.exceptions.BaseServerResponseException;
import org.hl7.fhir.instance.model.api.IIdType;
import org.hl7.fhir.r4.model.Bundle;
import org.hl7.fhir.r4.model.CapabilityStatement;
import org.hl7.fhir.r4.model.Condition;
import org.hl7.fhir.r4.model.Observation;
import org.hl7.fhir.r4.model.Patient;
import org.hl7.fhir.r4.model.Reference;
import org.hl7.fhir.r4.model.Resource;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;
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

    public Bundle searchPatientsByNameAndGender(String name, String gender) {
        requireText(name, "Patient name search parameter must be provided");
        requireText(gender, "Patient gender search parameter must be provided");
        return execute(
                () -> fhirClient.search()
                        .forResource(Patient.class)
                        .where(Patient.NAME.matches().value(name))
                        .and(Patient.GENDER.exactly().code(gender))
                        .returnBundle(Bundle.class)
                        .execute(),
                "searching Patient by name and gender");
    }

    public Bundle searchPatientsByNameExact(String name) {
        requireText(name, "Patient name search parameter must be provided");
        return execute(
                () -> fhirClient.search()
                        .forResource(Patient.class)
                        .where(Patient.NAME.matchesExactly().value(name))
                        .returnBundle(Bundle.class)
                        .execute(),
                "searching Patient by name:exact");
    }

    public Bundle searchPatientsBornOnOrAfter(String birthDate) {
        requireText(birthDate, "Patient birthdate search parameter must be provided");
        return execute(
                () -> fhirClient.search()
                        .forResource(Patient.class)
                        .where(Patient.BIRTHDATE.afterOrEquals().day(birthDate))
                        .returnBundle(Bundle.class)
                        .execute(),
                "searching Patient by birthdate=ge" + birthDate);
    }

    public Bundle searchPatientsBornBefore(String birthDate) {
        requireText(birthDate, "Patient birthdate search parameter must be provided");
        return execute(
                () -> fhirClient.search()
                        .forResource(Patient.class)
                        .where(Patient.BIRTHDATE.before().day(birthDate))
                        .returnBundle(Bundle.class)
                        .execute(),
                "searching Patient by birthdate=lt" + birthDate);
    }

    public Bundle searchPatientsSortedByBirthDateAscending() {
        return execute(
                () -> fhirClient.search()
                        .forResource(Patient.class)
                        .sort()
                        .ascending(Patient.BIRTHDATE)
                        .returnBundle(Bundle.class)
                        .execute(),
                "searching Patient with _sort=birthdate");
    }

    public Bundle searchPatientsSortedByBirthDateDescending() {
        return execute(
                () -> fhirClient.search()
                        .forResource(Patient.class)
                        .sort()
                        .descending(Patient.BIRTHDATE)
                        .returnBundle(Bundle.class)
                        .execute(),
                "searching Patient with _sort=-birthdate");
    }

    public Bundle searchPatientsWithCount(int pageSize) {
        if (pageSize < 1) {
            throw new IllegalArgumentException("Patient _count must be at least 1");
        }
        return execute(
                () -> fhirClient.search()
                        .forResource(Patient.class)
                        .count(pageSize)
                        .returnBundle(Bundle.class)
                        .execute(),
                "searching Patient with _count=" + pageSize);
    }

    public Bundle searchObservationsByPatientAndCode(String patientLogicalId, String code) {
        requireText(patientLogicalId, "Patient logical ID must be provided");
        requireText(code, "Observation code search parameter must be provided");
        return execute(
                () -> fhirClient.search()
                        .forResource(Observation.class)
                        .where(Observation.PATIENT.hasId(patientLogicalId))
                        .and(Observation.CODE.exactly().code(code))
                        .returnBundle(Bundle.class)
                        .execute(),
                "searching Observation by patient and code");
    }

    public Bundle searchObservationsByPatientAndCodeSortedByDate(
            String patientLogicalId,
            String code,
            int pageSize) {
        requireText(patientLogicalId, "Patient logical ID must be provided");
        requireText(code, "Observation code search parameter must be provided");
        if (pageSize < 1) {
            throw new IllegalArgumentException("Observation _count must be at least 1");
        }
        return execute(
                () -> fhirClient.search()
                        .forResource(Observation.class)
                        .where(Observation.PATIENT.hasId(patientLogicalId))
                        .and(Observation.CODE.exactly().code(code))
                        .sort()
                        .descending(Observation.DATE)
                        .count(pageSize)
                        .returnBundle(Bundle.class)
                        .execute(),
                "searching Observation by patient, code, _sort=-date, and _count");
    }

    public Bundle searchConditionsByPatientAndClinicalStatus(String patientLogicalId, String clinicalStatus) {
        requireText(patientLogicalId, "Patient logical ID must be provided");
        requireText(clinicalStatus, "Condition clinical-status search parameter must be provided");
        return execute(
                () -> fhirClient.search()
                        .forResource(Condition.class)
                        .where(Condition.PATIENT.hasId(patientLogicalId))
                        .and(Condition.CLINICAL_STATUS.exactly().code(clinicalStatus))
                        .returnBundle(Bundle.class)
                        .execute(),
                "searching Condition by patient and clinical-status");
    }

    public Bundle searchObservationsByPatientName(String patientName) {
        requireText(patientName, "Patient name search parameter must be provided");
        return execute(
                () -> fhirClient.search()
                        .forResource(Observation.class)
                        .where(Observation.PATIENT.hasChainedProperty(Patient.NAME.matches().value(patientName)))
                        .returnBundle(Bundle.class)
                        .execute(),
                "searching Observation by patient.name");
    }

    public Bundle searchObservationsByPatientNameAndCode(String patientName, String code) {
        requireText(patientName, "Patient name search parameter must be provided");
        requireText(code, "Observation code search parameter must be provided");
        return execute(
                () -> fhirClient.search()
                        .forResource(Observation.class)
                        .where(Observation.PATIENT.hasChainedProperty(Patient.NAME.matches().value(patientName)))
                        .and(Observation.CODE.exactly().code(code))
                        .returnBundle(Bundle.class)
                        .execute(),
                "searching Observation by patient.name and code");
    }

    public Bundle searchObservationsByPatientIdentifier(String identifier) {
        requireText(identifier, "Patient identifier search parameter must be provided");
        return execute(
                () -> fhirClient.search()
                        .forResource(Observation.class)
                        .where(Observation.PATIENT.hasChainedProperty(
                                Patient.IDENTIFIER.exactly().identifier(identifier)))
                        .returnBundle(Bundle.class)
                        .execute(),
                "searching Observation by patient.identifier");
    }

    public Bundle searchConditionsByPatientNameAndClinicalStatus(String patientName, String clinicalStatus) {
        requireText(patientName, "Patient name search parameter must be provided");
        requireText(clinicalStatus, "Condition clinical-status search parameter must be provided");
        return execute(
                () -> fhirClient.search()
                        .forResource(Condition.class)
                        .where(Condition.PATIENT.hasChainedProperty(Patient.NAME.matches().value(patientName)))
                        .and(Condition.CLINICAL_STATUS.exactly().code(clinicalStatus))
                        .returnBundle(Bundle.class)
                        .execute(),
                "searching Condition by patient.name and clinical-status");
    }

    public Bundle searchPatientsHavingObservationCode(String code) {
        requireText(code, "Observation code search parameter must be provided");
        return execute(
                () -> fhirClient.search()
                        .forResource(Patient.class)
                        .where(reverseChain("Observation", "patient", "code", code))
                        .returnBundle(Bundle.class)
                        .execute(),
                "searching Patient with _has:Observation:patient:code");
    }

    public Bundle searchPatientsHavingConditionClinicalStatus(String clinicalStatus) {
        requireText(clinicalStatus, "Condition clinical-status search parameter must be provided");
        return execute(
                () -> fhirClient.search()
                        .forResource(Patient.class)
                        .where(reverseChain("Condition", "patient", "clinical-status", clinicalStatus))
                        .returnBundle(Bundle.class)
                        .execute(),
                "searching Patient with _has:Condition:patient:clinical-status");
    }

    public Bundle searchPatientsHavingObservationCodeAndGender(String code, String gender) {
        requireText(code, "Observation code search parameter must be provided");
        requireText(gender, "Patient gender search parameter must be provided");
        return execute(
                () -> fhirClient.search()
                        .forResource(Patient.class)
                        .where(reverseChain("Observation", "patient", "code", code))
                        .and(Patient.GENDER.exactly().code(gender))
                        .returnBundle(Bundle.class)
                        .execute(),
                "searching Patient with _has Observation code and gender");
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

    public MethodOutcome createPatient(Patient patient) {
        requireResource(patient, "Patient must be provided");
        return execute(
                () -> fhirClient.create()
                        .resource(patient)
                        .execute(),
                "creating Patient");
    }

    public MethodOutcome updatePatient(Patient patient) {
        requireResource(patient, "Patient must be provided");
        String logicalId = requireLogicalId(patient, "Patient logical ID must be provided for update");
        return execute(
                () -> fhirClient.update()
                        .resource(patient)
                        .execute(),
                "updating Patient/" + logicalId);
    }

    public MethodOutcome deletePatient(String logicalId) {
        requireText(logicalId, "Patient logical ID must be provided");
        return execute(
                () -> fhirClient.delete()
                        .resourceById("Patient", logicalId)
                        .execute(),
                "deleting Patient/" + logicalId);
    }

    public MethodOutcome createObservation(Observation observation) {
        requireResource(observation, "Observation must be provided");
        return execute(
                () -> fhirClient.create()
                        .resource(observation)
                        .execute(),
                "creating Observation");
    }

    public MethodOutcome deleteObservation(String logicalId) {
        requireText(logicalId, "Observation logical ID must be provided");
        return execute(
                () -> fhirClient.delete()
                        .resourceById("Observation", logicalId)
                        .execute(),
                "deleting Observation/" + logicalId);
    }

    public String createdLogicalId(MethodOutcome outcome) {
        if (outcome == null) {
            throw new IllegalArgumentException("MethodOutcome must be provided");
        }
        IIdType id = outcome.getId();
        if (id == null || !id.hasIdPart()) {
            throw new IllegalArgumentException("MethodOutcome must contain a resource identity");
        }
        return id.getIdPart();
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

    private static void requireResource(Resource resource, String message) {
        if (resource == null) {
            throw new IllegalArgumentException(message);
        }
    }

    private static String requireLogicalId(Resource resource, String message) {
        String logicalId = resource.getIdElement().getIdPart();
        requireText(logicalId, message);
        return logicalId;
    }

    private static Map<String, List<IQueryParameterType>> reverseChain(
            String targetResourceType,
            String referenceSearchParam,
            String chainedSearchParam,
            String value) {
        return Map.of(
                "_has",
                List.of(new HasParam(targetResourceType, referenceSearchParam, chainedSearchParam, value)));
    }
}

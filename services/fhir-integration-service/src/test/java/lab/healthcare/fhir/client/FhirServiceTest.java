package lab.healthcare.fhir.client;

import ca.uhn.fhir.rest.api.MethodOutcome;
import ca.uhn.fhir.rest.client.api.IGenericClient;
import ca.uhn.fhir.rest.client.exceptions.FhirClientConnectionException;
import ca.uhn.fhir.rest.gclient.ICriterion;
import ca.uhn.fhir.rest.gclient.IParam;
import ca.uhn.fhir.rest.server.exceptions.InternalErrorException;
import ca.uhn.fhir.rest.server.exceptions.ResourceNotFoundException;
import org.hl7.fhir.r4.model.Bundle;
import org.hl7.fhir.r4.model.CapabilityStatement;
import org.hl7.fhir.r4.model.Condition;
import org.hl7.fhir.r4.model.Enumerations;
import org.hl7.fhir.r4.model.IdType;
import org.hl7.fhir.r4.model.Observation;
import org.hl7.fhir.r4.model.Patient;
import org.hl7.fhir.r4.model.Reference;
import org.hl7.fhir.r4.model.Resource;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Answers;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class FhirServiceTest {

    @Mock(answer = Answers.RETURNS_DEEP_STUBS)
    private IGenericClient fhirClient;

    @InjectMocks
    private FhirService fhirService;

    @Test
    void retrieveCapabilityStatementReturnsServerMetadata() {
        CapabilityStatement expected = new CapabilityStatement();
        expected.setFhirVersion(Enumerations.FHIRVersion._4_0_1);
        when(fhirClient.capabilities().ofType(CapabilityStatement.class).execute()).thenReturn(expected);

        CapabilityStatement actual = fhirService.retrieveCapabilityStatement();

        assertThat(actual).isSameAs(expected);
        assertThat(actual.getFhirVersion()).isEqualTo(Enumerations.FHIRVersion._4_0_1);
    }

    @Test
    void retrieveCapabilityStatementDoesNotSwallowConnectionErrors() {
        when(fhirClient.capabilities().ofType(CapabilityStatement.class).execute())
                .thenThrow(new FhirClientConnectionException("connection refused"));

        assertThatThrownBy(() -> fhirService.retrieveCapabilityStatement())
                .isInstanceOf(FhirClientException.class)
                .hasMessageContaining("Unable to connect")
                .hasCauseInstanceOf(FhirClientConnectionException.class);
    }

    @Test
    void retrieveCapabilityStatementDoesNotSwallowServerErrors() {
        when(fhirClient.capabilities().ofType(CapabilityStatement.class).execute())
                .thenThrow(new InternalErrorException("server error"));

        assertThatThrownBy(() -> fhirService.retrieveCapabilityStatement())
                .isInstanceOf(FhirClientException.class)
                .hasMessageContaining("returned an error")
                .hasCauseInstanceOf(InternalErrorException.class);
    }

    @Test
    void readPatientReturnsPatientResource() {
        Patient expected = syntheticPatient("patient-001", "Garcia", "Maria");
        when(fhirClient.read().resource(Patient.class).withId("patient-001").execute()).thenReturn(expected);

        Patient actual = fhirService.readPatient("patient-001");

        assertThat(actual.getIdElement().getIdPart()).isEqualTo("patient-001");
        assertThat(actual.getNameFirstRep().getFamily()).isEqualTo("Garcia");
        assertThat(actual.getNameFirstRep().getGivenAsSingleString()).isEqualTo("Maria");
    }

    @Test
    void readPatientDoesNotSwallowNotFound() {
        when(fhirClient.read().resource(Patient.class).withId("missing").execute())
                .thenThrow(new ResourceNotFoundException("Patient/missing"));

        assertThatThrownBy(() -> fhirService.readPatient("missing"))
                .isInstanceOf(FhirClientException.class)
                .hasCauseInstanceOf(ResourceNotFoundException.class);
    }

    @Test
    void searchPatientsByNameReturnsBundle() {
        Bundle expected = searchBundle(
                syntheticPatient("patient-001", "Garcia", "Maria"),
                syntheticPatient("patient-003", "Lopez", "Maria"));
        when(fhirClient.search()
                .forResource(eq(Patient.class))
                .where(any(ICriterion.class))
                .returnBundle(eq(Bundle.class))
                .execute())
                .thenReturn(expected);

        Bundle actual = fhirService.searchPatientsByName("Maria");

        assertThat(actual.getType()).isEqualTo(Bundle.BundleType.SEARCHSET);
        assertThat(fhirService.extractPatients(actual))
                .extracting(patient -> patient.getIdElement().getIdPart())
                .containsExactlyInAnyOrder("patient-001", "patient-003");
    }

    @Test
    void searchPatientsByIdentifierReturnsBundle() {
        Bundle expected = searchBundle(syntheticPatient("patient-001", "Garcia", "Maria"));
        when(fhirClient.search()
                .forResource(eq(Patient.class))
                .where(any(ICriterion.class))
                .returnBundle(eq(Bundle.class))
                .execute())
                .thenReturn(expected);

        Bundle actual = fhirService.searchPatientsByIdentifier("MRN-10001");

        List<Patient> patients = fhirService.extractPatients(actual);
        assertThat(patients).hasSize(1);
        assertThat(patients.getFirst().getIdElement().getIdPart()).isEqualTo("patient-001");
    }

    @Test
    void searchPatientsByNameDoesNotSwallowConnectionErrors() {
        when(fhirClient.search()
                .forResource(eq(Patient.class))
                .where(any(ICriterion.class))
                .returnBundle(eq(Bundle.class))
                .execute())
                .thenThrow(new FhirClientConnectionException("connection refused"));

        assertThatThrownBy(() -> fhirService.searchPatientsByName("Maria"))
                .isInstanceOf(FhirClientException.class)
                .hasCauseInstanceOf(FhirClientConnectionException.class);
    }

    @Test
    void extractPatientsReadsResourcesFromBundleEntries() {
        Bundle bundle = searchBundle(
                syntheticPatient("patient-001", "Garcia", "Maria"),
                syntheticPatient("patient-003", "Lopez", "Maria"));

        assertThat(fhirService.extractPatients(bundle))
                .extracting(Patient::getNameFirstRep)
                .extracting(name -> name.getGivenAsSingleString() + " " + name.getFamily())
                .containsExactly("Maria Garcia", "Maria Lopez");
    }

    @Test
    void readObservationReturnsResourceAndSubjectReference() {
        Observation expected = syntheticObservation("obs-001", "Patient/patient-001");
        when(fhirClient.read().resource(Observation.class).withId("obs-001").execute()).thenReturn(expected);

        Observation actual = fhirService.readObservation("obs-001");

        assertThat(actual.getIdElement().getIdPart()).isEqualTo("obs-001");
        assertThat(fhirService.subjectReference(actual.getSubject())).isEqualTo("Patient/patient-001");
        assertThat(actual.getCode().getCodingFirstRep().getSystem()).isEqualTo("http://loinc.org");
        assertThat(actual.getCode().getCodingFirstRep().getCode()).isEqualTo("85354-9");
    }

    @Test
    void readConditionReturnsResourceAndSubjectReference() {
        Condition expected = syntheticCondition("condition-001", "Patient/patient-001");
        when(fhirClient.read().resource(Condition.class).withId("condition-001").execute()).thenReturn(expected);

        Condition actual = fhirService.readCondition("condition-001");

        assertThat(actual.getIdElement().getIdPart()).isEqualTo("condition-001");
        assertThat(fhirService.subjectReference(actual.getSubject())).isEqualTo("Patient/patient-001");
        assertThat(actual.getCode().getCodingFirstRep().getSystem()).isEqualTo("http://snomed.info/sct");
        assertThat(actual.getCode().getCodingFirstRep().getCode()).isEqualTo("38341003");
    }

    @Test
    void searchObservationsByPatientReturnsBundle() {
        Bundle expected = searchBundle(syntheticObservation("obs-001", "Patient/patient-001"));
        when(fhirClient.search()
                .forResource(eq(Observation.class))
                .where(any(ICriterion.class))
                .returnBundle(eq(Bundle.class))
                .execute())
                .thenReturn(expected);

        Bundle actual = fhirService.searchObservationsByPatient("patient-001");

        assertThat(actual.getType()).isEqualTo(Bundle.BundleType.SEARCHSET);
        assertThat(fhirService.extractObservations(actual))
                .extracting(observation -> observation.getIdElement().getIdPart())
                .containsExactly("obs-001");
    }

    @Test
    void searchConditionsByPatientReturnsBundle() {
        Bundle expected = searchBundle(syntheticCondition("condition-001", "Patient/patient-001"));
        when(fhirClient.search()
                .forResource(eq(Condition.class))
                .where(any(ICriterion.class))
                .returnBundle(eq(Bundle.class))
                .execute())
                .thenReturn(expected);

        Bundle actual = fhirService.searchConditionsByPatient("patient-001");

        assertThat(actual.getType()).isEqualTo(Bundle.BundleType.SEARCHSET);
        assertThat(fhirService.extractConditions(actual))
                .extracting(condition -> condition.getIdElement().getIdPart())
                .containsExactly("condition-001");
    }

    @Test
    void readObservationDoesNotSwallowNotFound() {
        when(fhirClient.read().resource(Observation.class).withId("missing").execute())
                .thenThrow(new ResourceNotFoundException("Observation/missing"));

        assertThatThrownBy(() -> fhirService.readObservation("missing"))
                .isInstanceOf(FhirClientException.class)
                .hasCauseInstanceOf(ResourceNotFoundException.class);
    }

    @Test
    void searchObservationsByPatientDoesNotSwallowConnectionErrors() {
        when(fhirClient.search()
                .forResource(eq(Observation.class))
                .where(any(ICriterion.class))
                .returnBundle(eq(Bundle.class))
                .execute())
                .thenThrow(new FhirClientConnectionException("connection refused"));

        assertThatThrownBy(() -> fhirService.searchObservationsByPatient("patient-001"))
                .isInstanceOf(FhirClientException.class)
                .hasCauseInstanceOf(FhirClientConnectionException.class);
    }

    @Test
    void searchObservationsByPatientIncludingSubjectReturnsObservationAndPatient() {
        Bundle expected = searchBundle(
                syntheticObservation("obs-001", "Patient/patient-001"),
                syntheticPatient("patient-001", "Garcia", "Maria"));
        when(fhirClient.search()
                .forResource(eq(Observation.class))
                .where(any(ICriterion.class))
                .include(any())
                .returnBundle(eq(Bundle.class))
                .execute())
                .thenReturn(expected);

        Bundle actual = fhirService.searchObservationsByPatientIncludingSubject("patient-001");

        assertThat(actual.getType()).isEqualTo(Bundle.BundleType.SEARCHSET);
        assertThat(fhirService.resourceIdentities(actual))
                .containsExactlyInAnyOrder("Observation/obs-001", "Patient/patient-001");
    }

    @Test
    void searchPatientRevincludingObservationSubjectReturnsPatientAndObservation() {
        Bundle expected = searchBundle(
                syntheticPatient("patient-001", "Garcia", "Maria"),
                syntheticObservation("obs-001", "Patient/patient-001"));
        when(fhirClient.search()
                .forResource(eq(Patient.class))
                .where(any(ICriterion.class))
                .revInclude(any())
                .returnBundle(eq(Bundle.class))
                .execute())
                .thenReturn(expected);

        Bundle actual = fhirService.searchPatientRevincludingObservationSubject("patient-001");

        assertThat(fhirService.resourceIdentities(actual))
                .containsExactlyInAnyOrder("Patient/patient-001", "Observation/obs-001");
    }

    @Test
    void searchPatientRevincludingConditionSubjectReturnsPatientAndCondition() {
        Bundle expected = searchBundle(
                syntheticPatient("patient-001", "Garcia", "Maria"),
                syntheticCondition("condition-001", "Patient/patient-001"));
        when(fhirClient.search()
                .forResource(eq(Patient.class))
                .where(any(ICriterion.class))
                .revInclude(any())
                .returnBundle(eq(Bundle.class))
                .execute())
                .thenReturn(expected);

        Bundle actual = fhirService.searchPatientRevincludingConditionSubject("patient-001");

        assertThat(fhirService.resourceIdentities(actual))
                .containsExactlyInAnyOrder("Patient/patient-001", "Condition/condition-001");
    }

    @Test
    void searchPatientRevincludingObservationAndConditionSubjectReturnsAllThree() {
        Bundle expected = searchBundle(
                syntheticPatient("patient-001", "Garcia", "Maria"),
                syntheticObservation("obs-001", "Patient/patient-001"),
                syntheticCondition("condition-001", "Patient/patient-001"));
        when(fhirClient.search()
                .forResource(eq(Patient.class))
                .where(any(ICriterion.class))
                .revInclude(any())
                .revInclude(any())
                .returnBundle(eq(Bundle.class))
                .execute())
                .thenReturn(expected);

        Bundle actual = fhirService.searchPatientRevincludingObservationAndConditionSubject("patient-001");

        assertThat(fhirService.resourceIdentities(actual))
                .containsExactlyInAnyOrder(
                        "Patient/patient-001",
                        "Observation/obs-001",
                        "Condition/condition-001");
    }

    @Test
    void resourceIdentitiesReadsTypeAndIdFromMixedBundle() {
        Bundle bundle = searchBundle(
                syntheticCondition("condition-001", "Patient/patient-001"),
                syntheticPatient("patient-001", "Garcia", "Maria"),
                syntheticObservation("obs-001", "Patient/patient-001"));

        assertThat(fhirService.resourceIdentities(bundle))
                .containsExactly(
                        "Condition/condition-001",
                        "Patient/patient-001",
                        "Observation/obs-001");
    }

    @Test
    void searchObservationsByPatientIncludingSubjectDoesNotSwallowConnectionErrors() {
        when(fhirClient.search()
                .forResource(eq(Observation.class))
                .where(any(ICriterion.class))
                .include(any())
                .returnBundle(eq(Bundle.class))
                .execute())
                .thenThrow(new FhirClientConnectionException("connection refused"));

        assertThatThrownBy(() -> fhirService.searchObservationsByPatientIncludingSubject("patient-001"))
                .isInstanceOf(FhirClientException.class)
                .hasCauseInstanceOf(FhirClientConnectionException.class);
    }

    @Test
    void createPatientReturnsMethodOutcomeWithServerAssignedId() {
        Patient draft = new Patient();
        draft.addName().setFamily("Torres").addGiven("Ana");
        MethodOutcome expected = writeOutcome("Patient", "42", true);
        when(fhirClient.create().resource(any(Patient.class)).execute()).thenReturn(expected);

        MethodOutcome actual = fhirService.createPatient(draft);

        assertThat(actual).isSameAs(expected);
        assertThat(fhirService.createdLogicalId(actual)).isEqualTo("42");
        assertThat(actual.getCreated()).isTrue();
    }

    @Test
    void createPatientDoesNotSwallowServerErrors() {
        when(fhirClient.create().resource(any(Patient.class)).execute())
                .thenThrow(new InternalErrorException("server error"));

        assertThatThrownBy(() -> fhirService.createPatient(new Patient()))
                .isInstanceOf(FhirClientException.class)
                .hasMessageContaining("creating Patient")
                .hasCauseInstanceOf(InternalErrorException.class);
    }

    @Test
    void updatePatientSendsResourceWithLogicalId() {
        Patient patient = syntheticPatient("patient-write-001", "Mendoza", "Carlos");
        MethodOutcome expected = writeOutcome("Patient", "patient-write-001", false);
        when(fhirClient.update().resource(any(Patient.class)).execute()).thenReturn(expected);

        MethodOutcome actual = fhirService.updatePatient(patient);

        assertThat(actual).isSameAs(expected);
        assertThat(fhirService.createdLogicalId(actual)).isEqualTo("patient-write-001");
    }

    @Test
    void updatePatientRequiresLogicalId() {
        assertThatThrownBy(() -> fhirService.updatePatient(new Patient()))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("logical ID");
    }

    @Test
    void deletePatientReturnsOutcome() {
        MethodOutcome expected = writeOutcome("Patient", "42", false);
        when(fhirClient.delete().resourceById("Patient", "42").execute()).thenReturn(expected);

        MethodOutcome actual = fhirService.deletePatient("42");

        assertThat(actual).isSameAs(expected);
    }

    @Test
    void deletePatientDoesNotSwallowNotFound() {
        when(fhirClient.delete().resourceById("Patient", "missing").execute())
                .thenThrow(new ResourceNotFoundException("Patient/missing"));

        assertThatThrownBy(() -> fhirService.deletePatient("missing"))
                .isInstanceOf(FhirClientException.class)
                .hasCauseInstanceOf(ResourceNotFoundException.class);
    }

    @Test
    void createObservationReturnsMethodOutcomeWithServerAssignedId() {
        Observation draft = syntheticObservation(null, "Patient/patient-001");
        MethodOutcome expected = writeOutcome("Observation", "99", true);
        when(fhirClient.create().resource(any(Observation.class)).execute()).thenReturn(expected);

        MethodOutcome actual = fhirService.createObservation(draft);

        assertThat(fhirService.createdLogicalId(actual)).isEqualTo("99");
        assertThat(actual.getCreated()).isTrue();
    }

    @Test
    void createObservationDoesNotSwallowConnectionErrors() {
        when(fhirClient.create().resource(any(Observation.class)).execute())
                .thenThrow(new FhirClientConnectionException("connection refused"));

        assertThatThrownBy(() -> fhirService.createObservation(syntheticObservation(null, "Patient/patient-001")))
                .isInstanceOf(FhirClientException.class)
                .hasCauseInstanceOf(FhirClientConnectionException.class);
    }

    @Test
    void createdLogicalIdRequiresIdentity() {
        assertThatThrownBy(() -> fhirService.createdLogicalId(new MethodOutcome()))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("resource identity");
    }

    @Test
    void searchPatientsByNameAndGenderReturnsMatchingBundle() {
        Bundle expected = searchBundle(
                syntheticPatient("patient-001", "Garcia", "Maria"),
                syntheticPatient("patient-003", "Lopez", "Maria"));
        when(fhirClient.search()
                .forResource(eq(Patient.class))
                .where(any(ICriterion.class))
                .and(any(ICriterion.class))
                .returnBundle(eq(Bundle.class))
                .execute())
                .thenReturn(expected);

        Bundle actual = fhirService.searchPatientsByNameAndGender("Maria", "female");

        assertThat(actual.getType()).isEqualTo(Bundle.BundleType.SEARCHSET);
        assertThat(fhirService.extractPatients(actual))
                .extracting(patient -> patient.getIdElement().getIdPart())
                .containsExactlyInAnyOrder("patient-001", "patient-003");
    }

    @Test
    void searchObservationsByPatientAndCodeReturnsMatchingBundle() {
        Bundle expected = searchBundle(syntheticObservation("obs-001", "Patient/patient-001"));
        when(fhirClient.search()
                .forResource(eq(Observation.class))
                .where(any(ICriterion.class))
                .and(any(ICriterion.class))
                .returnBundle(eq(Bundle.class))
                .execute())
                .thenReturn(expected);

        Bundle actual = fhirService.searchObservationsByPatientAndCode("patient-001", "85354-9");

        assertThat(fhirService.extractObservations(actual))
                .extracting(observation -> observation.getIdElement().getIdPart())
                .containsExactly("obs-001");
    }

    @Test
    void searchConditionsByPatientAndClinicalStatusReturnsMatchingBundle() {
        Bundle expected = searchBundle(syntheticCondition("condition-001", "Patient/patient-001"));
        when(fhirClient.search()
                .forResource(eq(Condition.class))
                .where(any(ICriterion.class))
                .and(any(ICriterion.class))
                .returnBundle(eq(Bundle.class))
                .execute())
                .thenReturn(expected);

        Bundle actual = fhirService.searchConditionsByPatientAndClinicalStatus("patient-001", "active");

        assertThat(fhirService.extractConditions(actual))
                .extracting(condition -> condition.getIdElement().getIdPart())
                .containsExactly("condition-001");
    }

    @Test
    void searchPatientsByNameExactReturnsMatchingBundle() {
        Bundle expected = searchBundle(
                syntheticPatient("patient-001", "Garcia", "Maria"),
                syntheticPatient("patient-003", "Lopez", "Maria"));
        when(fhirClient.search()
                .forResource(eq(Patient.class))
                .where(any(ICriterion.class))
                .returnBundle(eq(Bundle.class))
                .execute())
                .thenReturn(expected);

        Bundle actual = fhirService.searchPatientsByNameExact("Maria");

        assertThat(fhirService.extractPatients(actual))
                .extracting(patient -> patient.getIdElement().getIdPart())
                .containsExactlyInAnyOrder("patient-001", "patient-003");
    }

    @Test
    void searchPatientsBornOnOrAfterReturnsMatchingBundle() {
        Bundle expected = searchBundle(
                syntheticPatient("patient-001", "Garcia", "Maria"),
                syntheticPatient("patient-003", "Lopez", "Maria"));
        when(fhirClient.search()
                .forResource(eq(Patient.class))
                .where(any(ICriterion.class))
                .returnBundle(eq(Bundle.class))
                .execute())
                .thenReturn(expected);

        Bundle actual = fhirService.searchPatientsBornOnOrAfter("1985-01-01");

        assertThat(fhirService.extractPatients(actual))
                .extracting(patient -> patient.getIdElement().getIdPart())
                .containsExactlyInAnyOrder("patient-001", "patient-003");
    }

    @Test
    void searchPatientsSortedByBirthDateAscendingReturnsOrderedBundle() {
        Bundle expected = searchBundle(
                syntheticPatient("patient-002", "Garcia", "Juan"),
                syntheticPatient("patient-001", "Garcia", "Maria"),
                syntheticPatient("patient-003", "Lopez", "Maria"));
        when(fhirClient.search()
                .forResource(eq(Patient.class))
                .sort()
                .ascending(any(IParam.class))
                .returnBundle(eq(Bundle.class))
                .execute())
                .thenReturn(expected);

        Bundle actual = fhirService.searchPatientsSortedByBirthDateAscending();

        assertThat(fhirService.extractPatients(actual))
                .extracting(patient -> patient.getIdElement().getIdPart())
                .containsExactly("patient-002", "patient-001", "patient-003");
    }

    @Test
    void searchPatientsWithCountReturnsPageSizedBundle() {
        Bundle expected = searchBundle(
                syntheticPatient("patient-001", "Garcia", "Maria"),
                syntheticPatient("patient-002", "Garcia", "Juan"));
        expected.setTotal(3);
        expected.addLink().setRelation(Bundle.LINK_NEXT).setUrl("http://localhost:8080/fhir?_getpages=example");
        when(fhirClient.search()
                .forResource(eq(Patient.class))
                .count(2)
                .returnBundle(eq(Bundle.class))
                .execute())
                .thenReturn(expected);

        Bundle actual = fhirService.searchPatientsWithCount(2);

        assertThat(actual.getTotal()).isEqualTo(3);
        assertThat(actual.getEntry()).hasSize(2);
        assertThat(actual.getLink(Bundle.LINK_NEXT)).isNotNull();
    }

    @Test
    void searchObservationsByPatientAndCodeSortedByDateReturnsMatchingBundle() {
        Bundle expected = searchBundle(syntheticObservation("obs-001", "Patient/patient-001"));
        when(fhirClient.search()
                .forResource(eq(Observation.class))
                .where(any(ICriterion.class))
                .and(any(ICriterion.class))
                .sort()
                .descending(any(IParam.class))
                .count(10)
                .returnBundle(eq(Bundle.class))
                .execute())
                .thenReturn(expected);

        Bundle actual = fhirService.searchObservationsByPatientAndCodeSortedByDate("patient-001", "85354-9", 10);

        assertThat(fhirService.extractObservations(actual))
                .extracting(observation -> observation.getIdElement().getIdPart())
                .containsExactly("obs-001");
    }

    @Test
    void searchPatientsByNameAndGenderDoesNotSwallowConnectionErrors() {
        when(fhirClient.search()
                .forResource(eq(Patient.class))
                .where(any(ICriterion.class))
                .and(any(ICriterion.class))
                .returnBundle(eq(Bundle.class))
                .execute())
                .thenThrow(new FhirClientConnectionException("connection refused"));

        assertThatThrownBy(() -> fhirService.searchPatientsByNameAndGender("Maria", "female"))
                .isInstanceOf(FhirClientException.class)
                .hasCauseInstanceOf(FhirClientConnectionException.class);
    }

    @Test
    void searchPatientsWithCountRejectsNonPositivePageSize() {
        assertThatThrownBy(() -> fhirService.searchPatientsWithCount(0))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("_count");
    }

    private static MethodOutcome writeOutcome(String resourceType, String logicalId, boolean created) {
        MethodOutcome outcome = new MethodOutcome();
        outcome.setId(new IdType(resourceType, logicalId));
        outcome.setCreated(created);
        return outcome;
    }

    private static Patient syntheticPatient(String logicalId, String family, String given) {
        Patient patient = new Patient();
        patient.setId(logicalId);
        patient.addName().setFamily(family).addGiven(given);
        return patient;
    }

    private static Observation syntheticObservation(String logicalId, String patientReference) {
        Observation observation = new Observation();
        if (logicalId != null) {
            observation.setId(logicalId);
        }
        observation.setStatus(Observation.ObservationStatus.FINAL);
        observation.getCode().addCoding()
                .setSystem("http://loinc.org")
                .setCode("85354-9")
                .setDisplay("Blood pressure panel");
        observation.setSubject(new Reference(patientReference));
        return observation;
    }

    private static Condition syntheticCondition(String logicalId, String patientReference) {
        Condition condition = new Condition();
        condition.setId(logicalId);
        condition.getCode().addCoding()
                .setSystem("http://snomed.info/sct")
                .setCode("38341003")
                .setDisplay("Hypertensive disorder");
        condition.setSubject(new Reference(patientReference));
        return condition;
    }

    private static Bundle searchBundle(Resource... resources) {
        Bundle bundle = new Bundle();
        bundle.setType(Bundle.BundleType.SEARCHSET);
        bundle.setTotal(resources.length);
        for (Resource resource : resources) {
            bundle.addEntry().setResource(resource);
        }
        return bundle;
    }
}

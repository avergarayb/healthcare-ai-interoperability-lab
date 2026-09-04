package lab.healthcare.fhir.client;

import lab.healthcare.fhir.auth.oauth2.OAuth2TokenException;
import lab.healthcare.fhir.exception.FhirClientException;
import lab.healthcare.fhir.exception.FhirErrorCategory;

import ca.uhn.fhir.rest.api.MethodOutcome;
import ca.uhn.fhir.rest.client.api.IGenericClient;
import ca.uhn.fhir.rest.client.exceptions.FhirClientConnectionException;
import ca.uhn.fhir.rest.gclient.ICriterion;
import ca.uhn.fhir.rest.gclient.IParam;
import ca.uhn.fhir.rest.gclient.IQuery;
import ca.uhn.fhir.rest.gclient.IUpdateTyped;
import ca.uhn.fhir.rest.server.exceptions.InternalErrorException;
import ca.uhn.fhir.rest.server.exceptions.ResourceNotFoundException;
import ca.uhn.fhir.rest.server.exceptions.ResourceVersionConflictException;
import org.hl7.fhir.r4.model.BooleanType;
import org.hl7.fhir.r4.model.Bundle;
import org.hl7.fhir.r4.model.CapabilityStatement;
import org.hl7.fhir.r4.model.CodeableConcept;
import org.hl7.fhir.r4.model.CodeSystem;
import org.hl7.fhir.r4.model.Coding;
import org.hl7.fhir.r4.model.Condition;
import org.hl7.fhir.r4.model.Enumerations;
import org.hl7.fhir.r4.model.IdType;
import org.hl7.fhir.r4.model.Observation;
import org.hl7.fhir.r4.model.OperationOutcome;
import org.hl7.fhir.r4.model.Parameters;
import org.hl7.fhir.r4.model.Patient;
import org.hl7.fhir.r4.model.Reference;
import org.hl7.fhir.r4.model.Resource;
import org.hl7.fhir.r4.model.StringType;
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
import static org.mockito.ArgumentMatchers.anyMap;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
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
                .hasMessage(FhirErrorCategory.CONNECTION_ERROR.safeMessage())
                .hasCauseInstanceOf(FhirClientConnectionException.class)
                .extracting(ex -> ((FhirClientException) ex).category())
                .isEqualTo(FhirErrorCategory.CONNECTION_ERROR);
    }

    @Test
    void retrieveCapabilityStatementDoesNotSwallowServerErrors() {
        when(fhirClient.capabilities().ofType(CapabilityStatement.class).execute())
                .thenThrow(new InternalErrorException("server error"));

        assertThatThrownBy(() -> fhirService.retrieveCapabilityStatement())
                .isInstanceOf(FhirClientException.class)
                .hasMessage(FhirErrorCategory.SERVER_ERROR.safeMessage())
                .hasCauseInstanceOf(InternalErrorException.class)
                .extracting(ex -> ((FhirClientException) ex).category())
                .isEqualTo(FhirErrorCategory.SERVER_ERROR);
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
                .hasMessage(FhirErrorCategory.NOT_FOUND.safeMessage())
                .hasCauseInstanceOf(ResourceNotFoundException.class)
                .extracting(ex -> ((FhirClientException) ex).category())
                .isEqualTo(FhirErrorCategory.NOT_FOUND);
    }

    @Test
    void readPatientClassifiesTimeoutSeparatelyFromConnectionFailure() {
        when(fhirClient.read().resource(Patient.class).withId("patient-001").execute())
                .thenThrow(new FhirClientConnectionException("read timed out", new java.net.SocketTimeoutException("Read timed out")));

        assertThatThrownBy(() -> fhirService.readPatient("patient-001"))
                .isInstanceOf(FhirClientException.class)
                .hasMessage(FhirErrorCategory.TIMEOUT.safeMessage())
                .hasCauseInstanceOf(FhirClientConnectionException.class)
                .extracting(ex -> ((FhirClientException) ex).category())
                .isEqualTo(FhirErrorCategory.TIMEOUT);
    }

    @Test
    void readPatientClassifiesOAuthFailureAsAuthenticationError() {
        when(fhirClient.read().resource(Patient.class).withId("patient-001").execute())
                .thenThrow(new OAuth2TokenException("OAuth token acquisition failed: HTTP 401 invalid_client"));

        assertThatThrownBy(() -> fhirService.readPatient("patient-001"))
                .isInstanceOf(FhirClientException.class)
                .hasMessage(FhirErrorCategory.AUTHENTICATION_ERROR.safeMessage())
                .hasCauseInstanceOf(OAuth2TokenException.class)
                .extracting(FhirClientException.class::cast)
                .satisfies(ex -> {
                    assertThat(ex.category()).isEqualTo(FhirErrorCategory.AUTHENTICATION_ERROR);
                    assertThat(ex.getMessage()).doesNotContain("invalid_client");
                    assertThat(ex.getMessage()).doesNotContain("access_token");
                    assertThat(ex.details().toLogLine()).doesNotContain("access_token");
                });
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
    void searchObservationsByPatientWithCountReturnsBundle() {
        Bundle expected = searchBundle(syntheticObservation("obs-001", "Patient/patient-001"));
        when(fhirClient.search()
                .forResource(eq(Observation.class))
                .where(any(ICriterion.class))
                .count(5)
                .returnBundle(eq(Bundle.class))
                .execute())
                .thenReturn(expected);

        Bundle actual = fhirService.searchObservationsByPatientWithCount("patient-001", 5);

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
    void searchConditionsByPatientWithCountReturnsBundle() {
        Bundle expected = searchBundle(syntheticCondition("condition-001", "Patient/patient-001"));
        when(fhirClient.search()
                .forResource(eq(Condition.class))
                .where(any(ICriterion.class))
                .count(5)
                .returnBundle(eq(Bundle.class))
                .execute())
                .thenReturn(expected);

        Bundle actual = fhirService.searchConditionsByPatientWithCount("patient-001", 5);

        assertThat(actual.getType()).isEqualTo(Bundle.BundleType.SEARCHSET);
        assertThat(fhirService.extractConditions(actual))
                .extracting(condition -> condition.getIdElement().getIdPart())
                .containsExactly("condition-001");
    }

    @Test
    void searchConditionsByPatientWithCountAndCategoryReturnsBundle() {
        Bundle expected = searchBundle(syntheticCondition("condition-001", "Patient/patient-001"));
        when(fhirClient.search()
                .forResource(eq(Condition.class))
                .where(any(ICriterion.class))
                .and(any(ICriterion.class))
                .count(5)
                .returnBundle(eq(Bundle.class))
                .execute())
                .thenReturn(expected);

        Bundle actual = fhirService.searchConditionsByPatientWithCount("patient-001", 5, "problem-list-item");

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
    void getPatientEverythingReturnsSearchsetBundle() {
        Bundle expected = searchBundle(
                syntheticPatient("patient-001", "Garcia", "Maria"),
                syntheticObservation("obs-001", "Patient/patient-001"),
                syntheticCondition("condition-001", "Patient/patient-001"));
        when(fhirClient.operation()
                .onInstance(any(IdType.class))
                .named("$everything")
                .withNoParameters(Parameters.class)
                .useHttpGet()
                .returnResourceType(Bundle.class)
                .execute())
                .thenReturn(expected);

        Bundle actual = fhirService.getPatientEverything("patient-001");

        assertThat(actual.getType()).isEqualTo(Bundle.BundleType.SEARCHSET);
        assertThat(fhirService.resourceIdentities(actual)).containsExactlyInAnyOrder(
                "Patient/patient-001",
                "Observation/obs-001",
                "Condition/condition-001");
    }

    @Test
    void getPatientEverythingRequiresLogicalId() {
        assertThatThrownBy(() -> fhirService.getPatientEverything(" "))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("logical ID");
    }

    @Test
    void getPatientEverythingDoesNotSwallowNotFound() {
        when(fhirClient.operation()
                .onInstance(any(IdType.class))
                .named("$everything")
                .withNoParameters(Parameters.class)
                .useHttpGet()
                .returnResourceType(Bundle.class)
                .execute())
                .thenThrow(new ResourceNotFoundException("Patient/missing"));

        assertThatThrownBy(() -> fhirService.getPatientEverything("missing"))
                .isInstanceOf(FhirClientException.class)
                .hasCauseInstanceOf(ResourceNotFoundException.class);
    }

    @Test
    void getPatientEverythingWithCountReusesNextPage() {
        Bundle page1 = searchBundle(syntheticPatient("patient-001", "Garcia", "Maria"));
        page1.setTotal(4);
        page1.addLink().setRelation(Bundle.LINK_NEXT).setUrl("http://localhost:8080/fhir?_getpages=everything-2");
        Bundle page2 = searchBundle(syntheticObservation("obs-001", "Patient/patient-001"));
        when(fhirClient.operation()
                .onInstance(any(IdType.class))
                .named("$everything")
                .withParameter(eq(Parameters.class), eq("_count"), any())
                .useHttpGet()
                .returnResourceType(Bundle.class)
                .execute())
                .thenReturn(page1);
        when(fhirClient.loadPage().next(page1).execute()).thenReturn(page2);

        Bundle actual = fhirService.getPatientEverything("patient-001", 1);
        Bundle next = fhirService.nextPage(actual);

        assertThat(actual.getEntry()).hasSize(1);
        assertThat(fhirService.hasNextPage(actual)).isTrue();
        assertThat(fhirService.resourceIdentities(next)).containsExactly("Observation/obs-001");
    }

    @Test
    void getPatientEverythingWithCountRequiresPositivePageSize() {
        assertThatThrownBy(() -> fhirService.getPatientEverything("patient-001", 0))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("_count");
    }

    @Test
    void getPatientEverythingByTypesFiltersResourceTypes() {
        Bundle expected = searchBundle(syntheticObservation("obs-001", "Patient/patient-001"));
        when(fhirClient.operation()
                .onInstance(any(IdType.class))
                .named("$everything")
                .withParameter(eq(Parameters.class), eq("_type"), any())
                .useHttpGet()
                .returnResourceType(Bundle.class)
                .execute())
                .thenReturn(expected);

        Bundle actual = fhirService.getPatientEverythingByTypes("patient-001", "Observation");

        assertThat(fhirService.resourceIdentities(actual)).containsExactly("Observation/obs-001");
        assertThat(fhirService.resourceIdentities(actual)).doesNotContain("Patient/patient-001");
    }

    @Test
    void getPatientEverythingByTypesRequiresType() {
        assertThatThrownBy(() -> fhirService.getPatientEverythingByTypes("patient-001"))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("_type");
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
                .hasMessage(FhirErrorCategory.SERVER_ERROR.safeMessage())
                .hasCauseInstanceOf(InternalErrorException.class)
                .extracting(ex -> ((FhirClientException) ex).category())
                .isEqualTo(FhirErrorCategory.SERVER_ERROR);
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
    void getPatientHistoryReturnsHistoryBundle() {
        Bundle expected = historyBundle(
                historyPatientEntry("history-patient-001", "3", "V3", "PUT", "200 OK"),
                historyPatientEntry("history-patient-001", "2", "V2", "PUT", "200 OK"),
                historyPatientEntry("history-patient-001", "1", "V1", "POST", "201 Created"));
        when(fhirClient.history().onInstance(any(IdType.class)).returnBundle(Bundle.class).execute())
                .thenReturn(expected);

        Bundle actual = fhirService.getPatientHistory("history-patient-001");

        assertThat(actual.getType()).isEqualTo(Bundle.BundleType.HISTORY);
        assertThat(fhirService.historyVersionIds(actual)).containsExactly("3", "2", "1");
        assertThat(fhirService.historyRequestMethods(actual)).containsExactly("PUT", "PUT", "POST");
        assertThat(fhirService.historyResponseStatuses(actual)).containsExactly("200 OK", "200 OK", "201 Created");
        assertThat(fhirService.extractPatients(actual).getFirst().getNameFirstRep().getGivenAsSingleString())
                .isEqualTo("V3");
    }

    @Test
    void getPatientHistoryRequiresLogicalId() {
        assertThatThrownBy(() -> fhirService.getPatientHistory(" "))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("logical ID");
    }

    @Test
    void getPatientHistoryDoesNotSwallowServerErrors() {
        when(fhirClient.history().onInstance(any(IdType.class)).returnBundle(Bundle.class).execute())
                .thenThrow(new ResourceNotFoundException("Patient/missing"));

        assertThatThrownBy(() -> fhirService.getPatientHistory("missing"))
                .isInstanceOf(FhirClientException.class)
                .hasCauseInstanceOf(ResourceNotFoundException.class);
    }

    @Test
    void getPatientHistoryWithCountAppliesPageSize() {
        Bundle expected = historyBundle(historyPatientEntry("history-patient-001", "3", "V3", "PUT", "200 OK"));
        expected.setTotal(3);
        expected.addLink().setRelation(Bundle.LINK_NEXT)
                .setUrl("http://localhost:8080/fhir/Patient/history-patient-001/_history?_count=1&_offset=1");
        when(fhirClient.history().onInstance(any(IdType.class)).returnBundle(Bundle.class).count(1).execute())
                .thenReturn(expected);

        Bundle actual = fhirService.getPatientHistory("history-patient-001", 1);

        assertThat(actual.getType()).isEqualTo(Bundle.BundleType.HISTORY);
        assertThat(actual.getEntry()).hasSize(1);
        assertThat(actual.getTotal()).isEqualTo(3);
        assertThat(fhirService.hasNextPage(actual)).isTrue();
    }

    @Test
    void getPatientHistoryWithCountRequiresPositivePageSize() {
        assertThatThrownBy(() -> fhirService.getPatientHistory("history-patient-001", 0))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("_count");
    }

    @Test
    void readPatientVersionReturnsHistoricalResource() {
        Patient expected = syntheticPatient("history-patient-001", "History", "V1");
        expected.getMeta().setVersionId("1");
        when(fhirClient.read().resource(Patient.class).withIdAndVersion("history-patient-001", "1").execute())
                .thenReturn(expected);

        Patient actual = fhirService.readPatientVersion("history-patient-001", "1");

        assertThat(actual.getIdElement().getIdPart()).isEqualTo("history-patient-001");
        assertThat(fhirService.patientVersionId(actual)).isEqualTo("1");
        assertThat(actual.getNameFirstRep().getGivenAsSingleString()).isEqualTo("V1");
    }

    @Test
    void readPatientVersionRequiresVersionId() {
        assertThatThrownBy(() -> fhirService.readPatientVersion("history-patient-001", " "))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("version ID");
    }

    @Test
    void patientVersionIdReadsMeta() {
        Patient patient = syntheticPatient("history-patient-001", "History", "V3");
        patient.getMeta().setVersionId("3");

        assertThat(fhirService.patientVersionId(patient)).isEqualTo("3");
    }

    @Test
    void patientVersionIdRequiresMetaVersion() {
        assertThatThrownBy(() -> fhirService.patientVersionId(syntheticPatient("history-patient-001", "History", "V3")))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("versionId");
    }

    @Test
    void currentReadAndVersionReadAreDistinctOperations() {
        Patient current = syntheticPatient("history-patient-001", "History", "V3");
        current.getMeta().setVersionId("3");
        Patient historical = syntheticPatient("history-patient-001", "History", "V1");
        historical.getMeta().setVersionId("1");
        when(fhirClient.read().resource(Patient.class).withId("history-patient-001").execute()).thenReturn(current);
        when(fhirClient.read().resource(Patient.class).withIdAndVersion("history-patient-001", "1").execute())
                .thenReturn(historical);

        Patient actualCurrent = fhirService.readPatient("history-patient-001");
        Patient actualHistorical = fhirService.readPatientVersion("history-patient-001", "1");

        assertThat(actualCurrent.getIdElement().getIdPart()).isEqualTo(actualHistorical.getIdElement().getIdPart());
        assertThat(fhirService.patientVersionId(actualCurrent)).isEqualTo("3");
        assertThat(fhirService.patientVersionId(actualHistorical)).isEqualTo("1");
        assertThat(actualCurrent.getNameFirstRep().getGivenAsSingleString()).isEqualTo("V3");
        assertThat(actualHistorical.getNameFirstRep().getGivenAsSingleString()).isEqualTo("V1");
    }

    @Test
    void historyVersionIdsUseRequestUrlWhenDeleteHasNoResource() {
        Bundle history = new Bundle();
        history.setType(Bundle.BundleType.HISTORY);
        Bundle.BundleEntryComponent deleted = history.addEntry();
        deleted.getRequest().setMethod(Bundle.HTTPVerb.DELETE).setUrl("Patient/history-delete-001/_history/2");
        deleted.getResponse().setStatus("200 OK").setEtag("W/\"2\"");
        history.addEntry().setResource(syntheticPatient("history-delete-001", "HistoryDelete", "Gone"))
                .getResource().getMeta().setVersionId("1");
        history.getEntry().get(1).getRequest().setMethod(Bundle.HTTPVerb.POST)
                .setUrl("Patient/history-delete-001/_history/1");
        history.getEntry().get(1).getResponse().setStatus("201 Created").setEtag("W/\"1\"");

        assertThat(fhirService.historyVersionIds(history)).containsExactly("2", "1");
        assertThat(fhirService.historyRequestMethods(history)).containsExactly("DELETE", "POST");
        assertThat(fhirService.extractPatients(history)).hasSize(1);
    }

    @Test
    void updatePatientIfMatchSendsVersionedUpdate() {
        Patient patient = syntheticPatient("history-patient-001", "History", "V4");
        MethodOutcome expected = writeOutcome("Patient", "history-patient-001", false);
        IUpdateTyped update = mock(IUpdateTyped.class);
        when(fhirClient.update().resource(any(Patient.class))).thenReturn(update);
        when(update.withAdditionalHeader("If-Match", "W/\"3\"")).thenReturn(update);
        when(update.execute()).thenReturn(expected);

        MethodOutcome actual = fhirService.updatePatientIfMatch(patient, "3");

        assertThat(actual).isSameAs(expected);
        assertThat(fhirService.createdLogicalId(actual)).isEqualTo("history-patient-001");
    }

    @Test
    void updatePatientIfMatchRequiresVersionId() {
        assertThatThrownBy(() -> fhirService.updatePatientIfMatch(
                syntheticPatient("history-patient-001", "History", "V4"), " "))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("version ID");
    }

    @Test
    void updatePatientIfMatchDoesNotSwallowVersionConflict() {
        IUpdateTyped update = mock(IUpdateTyped.class);
        when(fhirClient.update().resource(any(Patient.class))).thenReturn(update);
        when(update.withAdditionalHeader("If-Match", "W/\"999999\"")).thenReturn(update);
        when(update.execute()).thenThrow(new ResourceVersionConflictException("version conflict"));

        assertThatThrownBy(() -> fhirService.updatePatientIfMatch(
                syntheticPatient("history-patient-001", "History", "V4"), "999999"))
                .isInstanceOf(FhirClientException.class)
                .hasMessage(FhirErrorCategory.CONFLICT.safeMessage())
                .hasCauseInstanceOf(ResourceVersionConflictException.class)
                .extracting(ex -> ((FhirClientException) ex).category())
                .isEqualTo(FhirErrorCategory.CONFLICT);
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
    void searchPatientsByFamilyWithCountAppliesPageSize() {
        Bundle expected = searchBundle(
                syntheticPatient("pagelab-patient-001", "PageLab", "P001"),
                syntheticPatient("pagelab-patient-002", "PageLab", "P002"),
                syntheticPatient("pagelab-patient-003", "PageLab", "P003"));
        expected.setTotal(12);
        expected.addLink().setRelation(Bundle.LINK_SELF).setUrl("http://localhost:8080/fhir/Patient?family=PageLab&_count=3");
        expected.addLink().setRelation(Bundle.LINK_NEXT).setUrl("http://localhost:8080/fhir?_getpages=page-2");
        when(fhirClient.search()
                .forResource(eq(Patient.class))
                .where(any(ICriterion.class))
                .count(3)
                .returnBundle(eq(Bundle.class))
                .execute())
                .thenReturn(expected);

        Bundle actual = fhirService.searchPatientsByFamilyWithCount("PageLab", 3);

        assertThat(actual.getType()).isEqualTo(Bundle.BundleType.SEARCHSET);
        assertThat(actual.getTotal()).isEqualTo(12);
        assertThat(actual.getEntry()).hasSize(3);
        assertThat(fhirService.hasNextPage(actual)).isTrue();
        assertThat(fhirService.bundleLink(actual, Bundle.LINK_NEXT)).contains("_getpages");
    }

    @Test
    void nextPageFollowsServerProvidedLink() {
        Bundle page1 = searchBundle(syntheticPatient("pagination-patient-001", "Pagination", "Maria"));
        page1.addLink().setRelation(Bundle.LINK_NEXT).setUrl("http://localhost:8080/fhir?_getpages=page-2");
        Bundle page2 = searchBundle(syntheticPatient("pagination-patient-004", "Pagination", "P004"));
        page2.addLink().setRelation(Bundle.LINK_SELF).setUrl("http://localhost:8080/fhir?_getpages=page-2");
        when(fhirClient.loadPage().next(page1).execute()).thenReturn(page2);

        Bundle actual = fhirService.nextPage(page1);

        assertThat(fhirService.resourceIdentities(actual)).containsExactly("Patient/pagination-patient-004");
        assertThat(fhirService.bundleLink(actual, Bundle.LINK_SELF)).contains("_getpages=page-2");
    }

    @Test
    void nextPageRequiresNextLink() {
        Bundle lastPage = searchBundle(syntheticPatient("pagination-patient-012", "Pagination", "P012"));

        assertThatThrownBy(() -> fhirService.nextPage(lastPage))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("next");
        assertThat(fhirService.hasNextPage(lastPage)).isFalse();
    }

    @Test
    void fetchAllPagesWalksUntilThereIsNoNextLink() {
        Bundle page1 = searchBundle(syntheticPatient("pagination-patient-001", "Pagination", "Maria"));
        page1.addLink().setRelation(Bundle.LINK_NEXT).setUrl("http://localhost:8080/fhir?_getpages=page-2");
        Bundle page2 = searchBundle(syntheticPatient("pagination-patient-004", "Pagination", "P004"));
        when(fhirClient.loadPage().next(page1).execute()).thenReturn(page2);

        List<Bundle> pages = fhirService.fetchAllPages(page1);

        assertThat(pages).hasSize(2);
        assertThat(fhirService.resourceIdentities(pages.get(0))).containsExactly("Patient/pagination-patient-001");
        assertThat(fhirService.resourceIdentities(pages.get(1))).containsExactly("Patient/pagination-patient-004");
    }

    @Test
    void fetchAllPagesRejectsRepeatedNextUrl() {
        Bundle looping = searchBundle(syntheticPatient("pagination-patient-001", "Pagination", "Maria"));
        looping.addLink().setRelation(Bundle.LINK_NEXT).setUrl("http://localhost:8080/fhir?_getpages=loop");
        when(fhirClient.loadPage().next(looping).execute()).thenReturn(looping);

        assertThatThrownBy(() -> fhirService.fetchAllPages(looping))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("repeated");
    }

    @Test
    void nextPageDoesNotSwallowConnectionErrors() {
        Bundle page1 = searchBundle(syntheticPatient("pagination-patient-001", "Pagination", "Maria"));
        page1.addLink().setRelation(Bundle.LINK_NEXT).setUrl("http://localhost:8080/fhir?_getpages=page-2");
        when(fhirClient.loadPage().next(page1).execute())
                .thenThrow(new FhirClientConnectionException("connection refused"));

        assertThatThrownBy(() -> fhirService.nextPage(page1))
                .isInstanceOf(FhirClientException.class)
                .hasCauseInstanceOf(FhirClientConnectionException.class);
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

    @Test
    void searchObservationsByPatientNameReturnsMatchingBundle() {
        Bundle expected = searchBundle(syntheticObservation("obs-001", "Patient/patient-001"));
        when(fhirClient.search()
                .forResource(eq(Observation.class))
                .where(any(ICriterion.class))
                .returnBundle(eq(Bundle.class))
                .execute())
                .thenReturn(expected);

        Bundle actual = fhirService.searchObservationsByPatientName("Maria");

        assertThat(fhirService.resourceIdentities(actual)).containsExactly("Observation/obs-001");
    }

    @Test
    void searchObservationsByPatientNameAndCodeReturnsMatchingBundle() {
        Bundle expected = searchBundle(syntheticObservation("obs-001", "Patient/patient-001"));
        when(fhirClient.search()
                .forResource(eq(Observation.class))
                .where(any(ICriterion.class))
                .and(any(ICriterion.class))
                .returnBundle(eq(Bundle.class))
                .execute())
                .thenReturn(expected);

        Bundle actual = fhirService.searchObservationsByPatientNameAndCode("Maria", "85354-9");

        assertThat(fhirService.resourceIdentities(actual)).containsExactly("Observation/obs-001");
    }

    @Test
    void searchConditionsByPatientNameAndClinicalStatusReturnsMatchingBundle() {
        Bundle expected = searchBundle(syntheticCondition("condition-001", "Patient/patient-001"));
        when(fhirClient.search()
                .forResource(eq(Condition.class))
                .where(any(ICriterion.class))
                .and(any(ICriterion.class))
                .returnBundle(eq(Bundle.class))
                .execute())
                .thenReturn(expected);

        Bundle actual = fhirService.searchConditionsByPatientNameAndClinicalStatus("Maria", "active");

        assertThat(fhirService.resourceIdentities(actual)).containsExactly("Condition/condition-001");
    }

    @Test
    void searchObservationsByPatientIdentifierReturnsMatchingBundle() {
        Bundle expected = searchBundle(syntheticObservation("obs-001", "Patient/patient-001"));
        when(fhirClient.search()
                .forResource(eq(Observation.class))
                .where(any(ICriterion.class))
                .returnBundle(eq(Bundle.class))
                .execute())
                .thenReturn(expected);

        Bundle actual = fhirService.searchObservationsByPatientIdentifier("MRN-10001");

        assertThat(fhirService.resourceIdentities(actual)).containsExactly("Observation/obs-001");
    }

    @Test
    void searchPatientsHavingObservationCodeReturnsMatchingBundle() {
        Bundle expected = searchBundle(syntheticPatient("patient-001", "Garcia", "Maria"));
        stubPatientHasQuery(expected, false);

        Bundle actual = fhirService.searchPatientsHavingObservationCode("85354-9");

        assertThat(fhirService.resourceIdentities(actual)).containsExactly("Patient/patient-001");
    }

    @Test
    void searchPatientsHavingConditionClinicalStatusReturnsMatchingBundle() {
        Bundle expected = searchBundle(syntheticPatient("patient-001", "Garcia", "Maria"));
        stubPatientHasQuery(expected, false);

        Bundle actual = fhirService.searchPatientsHavingConditionClinicalStatus("active");

        assertThat(fhirService.resourceIdentities(actual)).containsExactly("Patient/patient-001");
    }

    @Test
    void searchPatientsHavingObservationCodeAndGenderReturnsMatchingBundle() {
        Bundle expected = searchBundle(syntheticPatient("patient-001", "Garcia", "Maria"));
        stubPatientHasQuery(expected, true);

        Bundle actual = fhirService.searchPatientsHavingObservationCodeAndGender("85354-9", "female");

        assertThat(fhirService.resourceIdentities(actual)).containsExactly("Patient/patient-001");
    }

    @Test
    void searchObservationsByPatientNameDoesNotSwallowConnectionErrors() {
        when(fhirClient.search()
                .forResource(eq(Observation.class))
                .where(any(ICriterion.class))
                .returnBundle(eq(Bundle.class))
                .execute())
                .thenThrow(new FhirClientConnectionException("connection refused"));

        assertThatThrownBy(() -> fhirService.searchObservationsByPatientName("Maria"))
                .isInstanceOf(FhirClientException.class)
                .hasCauseInstanceOf(FhirClientConnectionException.class);
    }

    @Test
    void searchPatientsHavingObservationCodeDoesNotSwallowConnectionErrors() {
        IQuery query = stubPatientHasQuery(searchBundle(), false);
        when(query.execute()).thenThrow(new FhirClientConnectionException("connection refused"));

        assertThatThrownBy(() -> fhirService.searchPatientsHavingObservationCode("85354-9"))
                .isInstanceOf(FhirClientException.class)
                .hasCauseInstanceOf(FhirClientConnectionException.class);
    }

    @SuppressWarnings({"unchecked", "rawtypes"})
    private IQuery stubPatientHasQuery(Bundle expected, boolean withAnd) {
        IQuery query = mock(IQuery.class);
        when(fhirClient.search().forResource(eq(Patient.class))).thenReturn(query);
        when(query.where(anyMap())).thenReturn(query);
        if (withAnd) {
            when(query.and(any(ICriterion.class))).thenReturn(query);
        }
        when(query.returnBundle(eq(Bundle.class))).thenReturn(query);
        when(query.execute()).thenReturn(expected);
        return query;
    }

    @Test
    void searchObservationsByCodeReturnsMatchingBundle() {
        Bundle expected = searchBundle(syntheticObservation("obs-001", "Patient/patient-001"));
        when(fhirClient.search()
                .forResource(eq(Observation.class))
                .where(any(ICriterion.class))
                .returnBundle(eq(Bundle.class))
                .execute())
                .thenReturn(expected);

        Bundle actual = fhirService.searchObservationsByCode("85354-9");

        assertThat(fhirService.resourceIdentities(actual)).containsExactly("Observation/obs-001");
    }

    @Test
    void validateCodeReturnsParametersForValidLoinc() {
        Parameters expected = validationParameters(true, "valid");
        stubValidateCode(expected);

        Parameters actual = fhirService.validateCode("http://loinc.org", "85354-9");

        assertThat(fhirService.validationResult(actual)).isTrue();
        assertThat(fhirService.validationMessage(actual)).isEqualTo("valid");
    }

    @Test
    void validateCodeReturnsParametersForInvalidLoinc() {
        Parameters expected = validationParameters(false, "unknown code");
        stubValidateCode(expected);

        Parameters actual = fhirService.validateCode("http://loinc.org", "99999999");

        assertThat(fhirService.validationResult(actual)).isFalse();
        assertThat(fhirService.validationMessage(actual)).contains("unknown");
    }

    @Test
    void validateCodeReturnsParametersForValidSnomed() {
        Parameters expected = validationParameters(true, "valid");
        stubValidateCode(expected);

        Parameters actual = fhirService.validateCode("http://snomed.info/sct", "38341003");

        assertThat(fhirService.validationResult(actual)).isTrue();
    }

    @Test
    void validateCodeReturnsParametersForInvalidSnomed() {
        Parameters expected = validationParameters(false, "not found");
        stubValidateCode(expected);

        Parameters actual = fhirService.validateCode("http://snomed.info/sct", "99999999");

        assertThat(fhirService.validationResult(actual)).isFalse();
    }

    @Test
    void validateCodeDoesNotSwallowConnectionErrors() {
        when(fhirClient.operation()
                .onType(CodeSystem.class)
                .named("$validate-code")
                .withParameter(eq(Parameters.class), eq("url"), any())
                .andParameter(eq("code"), any())
                .useHttpGet()
                .execute())
                .thenThrow(new FhirClientConnectionException("connection refused"));

        assertThatThrownBy(() -> fhirService.validateCode("http://loinc.org", "85354-9"))
                .isInstanceOf(FhirClientException.class)
                .hasCauseInstanceOf(FhirClientConnectionException.class);
    }

    @Test
    void validateResourceReturnsOperationOutcomeDetails() {
        Observation observation = syntheticObservation("obs-001", "Patient/patient-001");
        MethodOutcome expected = validationOutcome(
                OperationOutcome.IssueSeverity.WARNING,
                "CodeSystem is unknown and can't be validated: http://loinc.org");
        when(fhirClient.validate().resource(any(Observation.class)).execute()).thenReturn(expected);

        MethodOutcome actual = fhirService.validateResource(observation);
        OperationOutcome outcome = fhirService.operationOutcome(actual);

        assertThat(actual).isSameAs(expected);
        assertThat(fhirService.hasErrorIssue(outcome)).isFalse();
        assertThat(fhirService.issueDiagnostics(outcome)).containsExactly(
                "CodeSystem is unknown and can't be validated: http://loinc.org");
    }

    @Test
    void validateResourcePreservesErrorIssuesForInvalidObservation() {
        Observation invalid = new Observation();
        MethodOutcome expected = validationOutcome(
                OperationOutcome.IssueSeverity.ERROR,
                "Observation.status: minimum required = 1, but only found 0");
        when(fhirClient.validate().resource(any(Observation.class)).execute()).thenReturn(expected);

        OperationOutcome outcome = fhirService.operationOutcome(fhirService.validateResource(invalid));

        assertThat(fhirService.hasErrorIssue(outcome)).isTrue();
        assertThat(fhirService.issueDiagnostics(outcome)).anyMatch(diagnostics ->
                diagnostics.contains("Observation.status"));
    }

    @Test
    void validateResourceDoesNotSwallowConnectionErrors() {
        when(fhirClient.validate().resource(any(Observation.class)).execute())
                .thenThrow(new FhirClientConnectionException("connection refused"));

        assertThatThrownBy(() -> fhirService.validateResource(syntheticObservation("obs-001", "Patient/patient-001")))
                .isInstanceOf(FhirClientException.class)
                .hasCauseInstanceOf(FhirClientConnectionException.class);
    }

    @Test
    void validateResourceAgainstProfileReturnsProfileIssues() {
        Observation withoutSubject = syntheticObservation("obs-no-subject", "Patient/patient-001");
        withoutSubject.setSubject(null);
        MethodOutcome expected = validationOutcome(
                OperationOutcome.IssueSeverity.ERROR,
                "Observation.subject: minimum required = 1, but only found 0 (from https://example.org/fhir/StructureDefinition/lab-blood-pressure-observation)");
        when(fhirClient.validate().resource(any(Observation.class)).execute()).thenReturn(expected);

        OperationOutcome outcome = fhirService.operationOutcome(
                fhirService.validateResourceAgainstProfile(
                        withoutSubject,
                        "https://example.org/fhir/StructureDefinition/lab-blood-pressure-observation"));

        assertThat(fhirService.hasErrorIssue(outcome)).isTrue();
        assertThat(fhirService.issueDiagnostics(outcome)).anyMatch(diagnostics ->
                diagnostics.contains("lab-blood-pressure-observation"));
    }

    @Test
    void validateResourceAgainstProfilePreservesNonErrorIssues() {
        MethodOutcome expected = validationOutcome(
                OperationOutcome.IssueSeverity.WARNING,
                "Best Practice Recommendation: In general, all observations should have a performer");
        when(fhirClient.validate().resource(any(Observation.class)).execute()).thenReturn(expected);

        OperationOutcome outcome = fhirService.operationOutcome(
                fhirService.validateResourceAgainstProfile(
                        syntheticObservation("obs-001", "Patient/patient-001"),
                        "https://example.org/fhir/StructureDefinition/lab-blood-pressure-observation"));

        assertThat(fhirService.hasErrorIssue(outcome)).isFalse();
        assertThat(fhirService.issueDiagnostics(outcome)).isNotEmpty();
    }

    @Test
    void validateResourceAgainstProfileRequiresProfileUrl() {
        assertThatThrownBy(() -> fhirService.validateResourceAgainstProfile(
                        syntheticObservation("obs-001", "Patient/patient-001"), " "))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("Profile URL");
    }

    @Test
    void validateResourceAgainstProfileDoesNotSwallowConnectionErrors() {
        when(fhirClient.validate().resource(any(Observation.class)).execute())
                .thenThrow(new FhirClientConnectionException("connection refused"));

        assertThatThrownBy(() -> fhirService.validateResourceAgainstProfile(
                        syntheticObservation("obs-001", "Patient/patient-001"),
                        "https://example.org/fhir/StructureDefinition/lab-blood-pressure-observation"))
                .isInstanceOf(FhirClientException.class)
                .hasCauseInstanceOf(FhirClientConnectionException.class);
    }

    @Test
    void declaredProfilesReadMetaProfileWithoutValidating() {
        Observation observation = syntheticObservation("obs-001", "Patient/patient-001");
        observation.getMeta().addProfile("https://example.org/fhir/StructureDefinition/lab-blood-pressure-observation");

        assertThat(fhirService.declaredProfiles(observation)).containsExactly(
                "https://example.org/fhir/StructureDefinition/lab-blood-pressure-observation");
    }

    @Test
    void patientAndObservationCreateTransactionUsesTemporaryPatientReference() {
        Patient patient = syntheticPatient(null, "Vega", "Lucia");
        Observation observation = syntheticObservation(null, "Patient/ignored");

        Bundle bundle = fhirService.patientAndObservationCreateTransaction(patient, observation);

        assertThat(bundle.getType()).isEqualTo(Bundle.BundleType.TRANSACTION);
        assertThat(bundle.getEntry()).hasSize(2);
        assertThat(bundle.getEntry().get(0).getRequest().getMethod()).isEqualTo(Bundle.HTTPVerb.POST);
        assertThat(bundle.getEntry().get(0).getRequest().getUrl()).isEqualTo("Patient");
        assertThat(bundle.getEntry().get(0).getResource()).isInstanceOf(Patient.class);
        assertThat(bundle.getEntry().get(0).getFullUrl()).startsWith("urn:uuid:");
        assertThat(bundle.getEntry().get(1).getRequest().getMethod()).isEqualTo(Bundle.HTTPVerb.POST);
        assertThat(bundle.getEntry().get(1).getRequest().getUrl()).isEqualTo("Observation");
        Observation linked = (Observation) bundle.getEntry().get(1).getResource();
        assertThat(linked.getSubject().getReference()).isEqualTo(bundle.getEntry().get(0).getFullUrl());
    }

    @Test
    void patientCreateAndGetBatchUsesIndependentRequests() {
        Patient patient = syntheticPatient(null, "Batch", "Nuria");

        Bundle bundle = fhirService.patientCreateAndGetBatch(patient, "patient-001");

        assertThat(bundle.getType()).isEqualTo(Bundle.BundleType.BATCH);
        assertThat(bundle.getEntry()).hasSize(3);
        assertThat(bundle.getEntry().get(0).getRequest().getMethod()).isEqualTo(Bundle.HTTPVerb.POST);
        assertThat(bundle.getEntry().get(0).getRequest().getUrl()).isEqualTo("Patient");
        assertThat(bundle.getEntry().get(1).getRequest().getMethod()).isEqualTo(Bundle.HTTPVerb.GET);
        assertThat(bundle.getEntry().get(1).getRequest().getUrl()).isEqualTo("Patient/this-patient-does-not-exist-batch");
        assertThat(bundle.getEntry().get(2).getRequest().getMethod()).isEqualTo(Bundle.HTTPVerb.GET);
        assertThat(bundle.getEntry().get(2).getRequest().getUrl()).isEqualTo("Patient/patient-001");
    }

    @Test
    void conditionalCreatePatientTransactionSetsIfNoneExist() {
        Patient patient = syntheticPatient(null, "Garcia", "Maria");
        patient.addIdentifier().setSystem("https://example.org/lab/mrn").setValue("MRN-10001");

        Bundle bundle = fhirService.conditionalCreatePatientTransaction(patient);

        assertThat(bundle.getType()).isEqualTo(Bundle.BundleType.TRANSACTION);
        assertThat(bundle.getEntry()).hasSize(1);
        assertThat(bundle.getEntry().get(0).getRequest().getMethod()).isEqualTo(Bundle.HTTPVerb.POST);
        assertThat(bundle.getEntry().get(0).getRequest().getUrl()).isEqualTo("Patient");
        assertThat(bundle.getEntry().get(0).getRequest().getIfNoneExist())
                .isEqualTo("identifier=https://example.org/lab/mrn|MRN-10001");
    }

    @Test
    void executeTransactionSendsBundleAndPreservesResponseEntries() {
        Bundle request = fhirService.patientAndObservationCreateTransaction(
                syntheticPatient(null, "Vega", "Lucia"),
                syntheticObservation(null, "Patient/ignored"));
        Bundle expected = transactionResponse("201 Created", "Patient/42/_history/1");
        when(fhirClient.transaction().withBundle(any(Bundle.class)).execute()).thenReturn(expected);

        Bundle actual = fhirService.executeTransaction(request);

        assertThat(actual.getType()).isEqualTo(Bundle.BundleType.TRANSACTIONRESPONSE);
        assertThat(fhirService.entryResponseStatuses(actual)).containsExactly("201 Created");
        assertThat(fhirService.logicalIdFromLocation(fhirService.entryResponseLocation(actual, 0))).isEqualTo("42");
    }

    @Test
    void executeBatchRequiresBatchType() {
        Bundle transaction = new Bundle();
        transaction.setType(Bundle.BundleType.TRANSACTION);

        assertThatThrownBy(() -> fhirService.executeBatch(transaction))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("batch");
    }

    @Test
    void executeTransactionDoesNotSwallowConnectionErrors() {
        Bundle request = new Bundle();
        request.setType(Bundle.BundleType.TRANSACTION);
        when(fhirClient.transaction().withBundle(any(Bundle.class)).execute())
                .thenThrow(new FhirClientConnectionException("connection refused"));

        assertThatThrownBy(() -> fhirService.executeTransaction(request))
                .isInstanceOf(FhirClientException.class)
                .hasCauseInstanceOf(FhirClientConnectionException.class);
    }

    @Test
    void primaryCodingReadsSystemCodeAndDisplay() {
        Observation observation = syntheticObservation("obs-001", "Patient/patient-001");

        Coding coding = fhirService.primaryCoding(observation.getCode());

        assertThat(coding.getSystem()).isEqualTo("http://loinc.org");
        assertThat(coding.getCode()).isEqualTo("85354-9");
        assertThat(coding.getDisplay()).isEqualTo("Blood pressure panel");
    }

    @Test
    void codeableConceptCanHoldMultipleCodingsWithoutEquivalence() {
        CodeableConcept concept = new CodeableConcept();
        concept.addCoding()
                .setSystem("http://loinc.org")
                .setCode("85354-9")
                .setDisplay("Blood pressure panel");
        concept.addCoding()
                .setSystem("http://snomed.info/sct")
                .setCode("75367002")
                .setDisplay("Blood pressure");

        assertThat(concept.getCoding()).hasSize(2);
        assertThat(concept.getCoding().get(0).getSystem()).isNotEqualTo(concept.getCoding().get(1).getSystem());
    }

    @SuppressWarnings({"unchecked", "rawtypes"})
    private void stubValidateCode(Parameters expected) {
        when(fhirClient.operation()
                .onType(CodeSystem.class)
                .named("$validate-code")
                .withParameter(eq(Parameters.class), eq("url"), any())
                .andParameter(eq("code"), any())
                .useHttpGet()
                .execute())
                .thenReturn(expected);
    }

    private static Parameters validationParameters(boolean result, String message) {
        Parameters parameters = new Parameters();
        parameters.addParameter().setName("result").setValue(new BooleanType(result));
        parameters.addParameter().setName("message").setValue(new StringType(message));
        return parameters;
    }

    private static MethodOutcome validationOutcome(OperationOutcome.IssueSeverity severity, String diagnostics) {
        OperationOutcome operationOutcome = new OperationOutcome();
        operationOutcome.addIssue()
                .setSeverity(severity)
                .setCode(OperationOutcome.IssueType.PROCESSING)
                .setDiagnostics(diagnostics);
        MethodOutcome outcome = new MethodOutcome();
        outcome.setOperationOutcome(operationOutcome);
        return outcome;
    }

    private static Bundle transactionResponse(String status, String location) {
        Bundle bundle = new Bundle();
        bundle.setType(Bundle.BundleType.TRANSACTIONRESPONSE);
        bundle.addEntry().getResponse().setStatus(status).setLocation(location);
        return bundle;
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

    private static Bundle historyBundle(Bundle.BundleEntryComponent... entries) {
        Bundle bundle = new Bundle();
        bundle.setType(Bundle.BundleType.HISTORY);
        bundle.setTotal(entries.length);
        for (Bundle.BundleEntryComponent entry : entries) {
            bundle.addEntry(entry);
        }
        return bundle;
    }

    private static Bundle.BundleEntryComponent historyPatientEntry(
            String logicalId,
            String versionId,
            String given,
            String method,
            String status) {
        Patient patient = syntheticPatient(logicalId, "History", given);
        patient.getMeta().setVersionId(versionId);
        Bundle.BundleEntryComponent entry = new Bundle.BundleEntryComponent();
        entry.setResource(patient);
        entry.getRequest().setMethod(Bundle.HTTPVerb.fromCode(method)).setUrl("Patient/" + logicalId + "/_history/" + versionId);
        entry.getResponse().setStatus(status).setEtag("W/\"" + versionId + "\"");
        return entry;
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

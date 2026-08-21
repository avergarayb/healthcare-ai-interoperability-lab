package lab.healthcare.fhir.client;

import ca.uhn.fhir.rest.client.api.IGenericClient;
import ca.uhn.fhir.rest.client.exceptions.FhirClientConnectionException;
import ca.uhn.fhir.rest.gclient.ICriterion;
import ca.uhn.fhir.rest.server.exceptions.InternalErrorException;
import ca.uhn.fhir.rest.server.exceptions.ResourceNotFoundException;
import org.hl7.fhir.r4.model.Bundle;
import org.hl7.fhir.r4.model.CapabilityStatement;
import org.hl7.fhir.r4.model.Enumerations;
import org.hl7.fhir.r4.model.Patient;
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

    private static Patient syntheticPatient(String logicalId, String family, String given) {
        Patient patient = new Patient();
        patient.setId(logicalId);
        patient.addName().setFamily(family).addGiven(given);
        return patient;
    }

    private static Bundle searchBundle(Patient... patients) {
        Bundle bundle = new Bundle();
        bundle.setType(Bundle.BundleType.SEARCHSET);
        bundle.setTotal(patients.length);
        for (Patient patient : patients) {
            bundle.addEntry().setResource(patient);
        }
        return bundle;
    }
}

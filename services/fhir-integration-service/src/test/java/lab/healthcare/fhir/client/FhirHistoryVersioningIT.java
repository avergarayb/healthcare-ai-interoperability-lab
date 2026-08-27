package lab.healthcare.fhir.client;

import lab.healthcare.fhir.exception.FhirClientException;

import ca.uhn.fhir.rest.api.MethodOutcome;
import ca.uhn.fhir.rest.client.api.IGenericClient;
import ca.uhn.fhir.rest.server.exceptions.BaseServerResponseException;
import ca.uhn.fhir.rest.server.exceptions.ResourceGoneException;
import ca.uhn.fhir.rest.server.exceptions.ResourceVersionConflictException;
import org.hl7.fhir.r4.model.Bundle;
import org.hl7.fhir.r4.model.DateType;
import org.hl7.fhir.r4.model.Enumerations;
import org.hl7.fhir.r4.model.Patient;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestInstance;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
class FhirHistoryVersioningIT {

    @Autowired
    private FhirService fhirService;

    @Autowired
    private IGenericClient fhirClient;

    @BeforeAll
    void seedSyntheticHistory() {
        SyntheticPatients.seed(fhirClient);
        SyntheticHistoryPatients.seed(fhirClient);
    }

    @Test
    void createThenTwoUpdatesKeepLogicalIdAndChangeVersionIds() {
        MethodOutcome created = fhirService.createPatient(freshPatient("CreateHist", "MRN-HIST-NEW"));
        String logicalId = fhirService.createdLogicalId(created);
        Patient v1 = fhirService.readPatient(logicalId);
        String version1 = fhirService.patientVersionId(v1);

        v1.getNameFirstRep().getGiven().clear();
        v1.getNameFirstRep().addGiven("UpdateOne");
        fhirService.updatePatient(v1);
        Patient v2 = fhirService.readPatient(logicalId);
        String version2 = fhirService.patientVersionId(v2);

        v2.getNameFirstRep().getGiven().clear();
        v2.getNameFirstRep().addGiven("UpdateTwo");
        fhirService.updatePatient(v2);
        Patient v3 = fhirService.readPatient(logicalId);
        String version3 = fhirService.patientVersionId(v3);

        assertThat(v1.getIdElement().getIdPart()).isEqualTo(logicalId);
        assertThat(v2.getIdElement().getIdPart()).isEqualTo(logicalId);
        assertThat(v3.getIdElement().getIdPart()).isEqualTo(logicalId);
        assertThat(List.of(version1, version2, version3)).doesNotHaveDuplicates();
        assertThat(v3.getNameFirstRep().getGivenAsSingleString()).isEqualTo("UpdateTwo");
    }

    @Test
    void instanceHistoryReturnsHistoryBundleWithRequestAndResponse() {
        Bundle history = fhirService.getPatientHistory(SyntheticHistoryPatients.HISTORY_ID);

        assertThat(history.getType()).isEqualTo(Bundle.BundleType.HISTORY);
        assertThat(history.getEntry()).isNotEmpty();
        assertThat(history.getTotal()).isGreaterThanOrEqualTo(3);
        assertThat(fhirService.historyRequestMethods(history)).isNotEmpty();
        assertThat(fhirService.historyResponseStatuses(history)).isNotEmpty();
        assertThat(fhirService.historyVersionIds(history)).doesNotHaveDuplicates();
        assertThat(fhirService.extractPatients(history).stream()
                .map(patient -> patient.getNameFirstRep().getGivenAsSingleString())
                .toList())
                .contains(
                        SyntheticHistoryPatients.GIVEN_V1,
                        SyntheticHistoryPatients.GIVEN_V2,
                        SyntheticHistoryPatients.GIVEN_V3);
        history.getEntry().forEach(entry -> {
            assertThat(entry.hasRequest()).isTrue();
            assertThat(entry.hasResponse()).isTrue();
            assertThat(entry.getResponse().hasStatus()).isTrue();
            assertThat(entry.getResponse().hasEtag()).isTrue();
        });
    }

    @Test
    void versionSpecificReadReturnsHistoricalGivenName() {
        Bundle history = fhirService.getPatientHistory(SyntheticHistoryPatients.HISTORY_ID);
        Patient historical = fhirService.extractPatients(history).stream()
                .filter(patient -> SyntheticHistoryPatients.GIVEN_V1.equals(
                        patient.getNameFirstRep().getGivenAsSingleString()))
                .findFirst()
                .orElseThrow();
        String versionId = fhirService.patientVersionId(historical);

        Patient read = fhirService.readPatientVersion(SyntheticHistoryPatients.HISTORY_ID, versionId);

        assertThat(read.getIdElement().getIdPart()).isEqualTo(SyntheticHistoryPatients.HISTORY_ID);
        assertThat(fhirService.patientVersionId(read)).isEqualTo(versionId);
        assertThat(read.getNameFirstRep().getGivenAsSingleString()).isEqualTo(SyntheticHistoryPatients.GIVEN_V1);
        assertThat(read.getIdentifierFirstRep().getValue()).isEqualTo("MRN-HIST-001");
    }

    @Test
    void currentReadIsLatestVersionNotAHistoricalSnapshot() {
        Patient current = fhirService.readPatient(SyntheticHistoryPatients.HISTORY_ID);
        Bundle history = fhirService.getPatientHistory(SyntheticHistoryPatients.HISTORY_ID);
        Patient historicalV1 = fhirService.extractPatients(history).stream()
                .filter(patient -> SyntheticHistoryPatients.GIVEN_V1.equals(
                        patient.getNameFirstRep().getGivenAsSingleString()))
                .findFirst()
                .orElseThrow();

        assertThat(current.getIdElement().getIdPart()).isEqualTo(historicalV1.getIdElement().getIdPart());
        assertThat(current.getNameFirstRep().getGivenAsSingleString()).isEqualTo(SyntheticHistoryPatients.GIVEN_V3);
        assertThat(fhirService.patientVersionId(current)).isNotEqualTo(fhirService.patientVersionId(historicalV1));
        assertThat(current.getNameFirstRep().getFamily()).isEqualTo(historicalV1.getNameFirstRep().getFamily());
    }

    @Test
    void deleteRemovesCurrentReadButKeepsHistory() {
        fhirService.updatePatient(SyntheticHistoryPatients.patient(
                SyntheticHistoryPatients.DELETE_ID, "MRN-HIST-DEL-001", "Gone"));

        Patient beforeDelete = fhirService.readPatient(SyntheticHistoryPatients.DELETE_ID);
        assertThat(beforeDelete.getNameFirstRep().getGivenAsSingleString()).isEqualTo("Gone");

        fhirService.deletePatient(SyntheticHistoryPatients.DELETE_ID);

        assertThatThrownBy(() -> fhirService.readPatient(SyntheticHistoryPatients.DELETE_ID))
                .isInstanceOf(FhirClientException.class)
                .cause()
                .isInstanceOf(ResourceGoneException.class)
                .extracting(cause -> ((BaseServerResponseException) cause).getStatusCode())
                .isEqualTo(410);

        Bundle history = fhirService.getPatientHistory(SyntheticHistoryPatients.DELETE_ID);
        assertThat(history.getType()).isEqualTo(Bundle.BundleType.HISTORY);
        assertThat(fhirService.historyRequestMethods(history)).contains("DELETE");
        Bundle.BundleEntryComponent deleteEntry = history.getEntry().stream()
                .filter(entry -> entry.hasRequest() && entry.getRequest().getMethod() == Bundle.HTTPVerb.DELETE)
                .findFirst()
                .orElseThrow();
        assertThat(deleteEntry.hasResource()).isFalse();
        assertThat(deleteEntry.getResponse().getStatus()).contains("200");
        assertThat(fhirService.extractPatients(history)).isNotEmpty();
    }

    @Test
    void ifMatchAcceptsCurrentVersionAndRejectsStaleVersion() {
        MethodOutcome created = fhirService.createPatient(freshPatient("IfMatch", "MRN-HIST-IFMATCH"));
        String logicalId = fhirService.createdLogicalId(created);
        Patient current = fhirService.readPatient(logicalId);
        String currentVersion = fhirService.patientVersionId(current);

        current.getNameFirstRep().getGiven().clear();
        current.getNameFirstRep().addGiven("Matched");
        MethodOutcome accepted = fhirService.updatePatientIfMatch(current, currentVersion);
        Patient afterMatch = fhirService.readPatient(logicalId);

        assertThat(fhirService.createdLogicalId(accepted)).isEqualTo(logicalId);
        assertThat(afterMatch.getNameFirstRep().getGivenAsSingleString()).isEqualTo("Matched");
        assertThat(fhirService.patientVersionId(afterMatch)).isNotEqualTo(currentVersion);

        afterMatch.getNameFirstRep().getGiven().clear();
        afterMatch.getNameFirstRep().addGiven("Stale");
        assertThatThrownBy(() -> fhirService.updatePatientIfMatch(afterMatch, "999999"))
                .isInstanceOf(FhirClientException.class)
                .cause()
                .isInstanceOf(ResourceVersionConflictException.class)
                .extracting(cause -> ((BaseServerResponseException) cause).getStatusCode())
                .isEqualTo(409);
        assertThat(fhirService.readPatient(logicalId).getNameFirstRep().getGivenAsSingleString())
                .isEqualTo("Matched");
    }

    @Test
    void historyPaginationExposesNextLink() {
        Bundle page = fhirService.getPatientHistory(SyntheticHistoryPatients.HISTORY_ID, 1);

        assertThat(page.getType()).isEqualTo(Bundle.BundleType.HISTORY);
        assertThat(page.getEntry()).hasSize(1);
        assertThat(page.getTotal()).isGreaterThan(1);
        assertThat(fhirService.hasNextPage(page)).isTrue();
        assertThat(fhirService.bundleLink(page, Bundle.LINK_NEXT)).contains("_offset=");

        Bundle page2 = fhirService.nextPage(page);
        assertThat(page2.getType()).isEqualTo(Bundle.BundleType.HISTORY);
        assertThat(fhirService.historyVersionIds(page2)).isNotEmpty();
        assertThat(fhirService.historyVersionIds(page2)).doesNotContainAnyElementsOf(fhirService.historyVersionIds(page));
    }

    @Test
    void searchsetAndHistoryAreDifferentBundleTypes() {
        Bundle searchset = fhirService.searchPatientsByName("Maria");
        Bundle history = fhirService.getPatientHistory("patient-001");

        assertThat(searchset.getType()).isEqualTo(Bundle.BundleType.SEARCHSET);
        assertThat(history.getType()).isEqualTo(Bundle.BundleType.HISTORY);
    }

    @Test
    void typeAndSystemHistoryAreSupportedAndPaged() {
        Bundle typeHistory = fhirClient.history()
                .onType(Patient.class)
                .returnBundle(Bundle.class)
                .count(2)
                .execute();
        Bundle systemHistory = fhirClient.history()
                .onServer()
                .returnBundle(Bundle.class)
                .count(2)
                .execute();

        assertThat(typeHistory.getType()).isEqualTo(Bundle.BundleType.HISTORY);
        assertThat(typeHistory.getEntry()).hasSize(2);
        assertThat(fhirService.hasNextPage(typeHistory)).isTrue();
        assertThat(systemHistory.getType()).isEqualTo(Bundle.BundleType.HISTORY);
        assertThat(systemHistory.getEntry()).hasSize(2);
        assertThat(fhirService.hasNextPage(systemHistory)).isTrue();
    }

    private static Patient freshPatient(String family, String mrn) {
        Patient patient = new Patient();
        patient.addIdentifier().setSystem(SyntheticHistoryPatients.IDENTIFIER_SYSTEM).setValue(mrn);
        patient.addName().setFamily(family).addGiven("One");
        patient.setGender(Enumerations.AdministrativeGender.FEMALE);
        patient.setBirthDateElement(new DateType("1988-03-21"));
        return patient;
    }
}

package lab.healthcare.fhir.projection;

import lab.healthcare.fhir.auth.AccessToken;
import lab.healthcare.fhir.auth.IssuedAccessTokenProvider;
import lab.healthcare.fhir.capability.FhirCapabilityDiscoveryService;
import lab.healthcare.fhir.capability.FhirServerCapabilities;
import lab.healthcare.fhir.exception.FhirClientException;
import lab.healthcare.fhir.patient.PatientContextSource;
import lab.healthcare.fhir.routing.RoutingService;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotOutcome;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotResourceStatus;

import ca.uhn.fhir.rest.client.exceptions.FhirClientConnectionException;
import ca.uhn.fhir.rest.server.exceptions.AuthenticationException;
import ca.uhn.fhir.rest.server.exceptions.ForbiddenOperationException;
import org.hl7.fhir.r4.model.Bundle;
import org.hl7.fhir.r4.model.CapabilityStatement;
import org.hl7.fhir.r4.model.CodeableConcept;
import org.hl7.fhir.r4.model.Coding;
import org.hl7.fhir.r4.model.Condition;
import org.hl7.fhir.r4.model.DiagnosticReport;
import org.hl7.fhir.r4.model.Enumerations;
import org.hl7.fhir.r4.model.MedicationRequest;
import org.hl7.fhir.r4.model.Observation;
import org.hl7.fhir.r4.model.Patient;
import org.hl7.fhir.r4.model.Resource;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.net.SocketTimeoutException;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class ClinicalProjectionAssemblerTest {

    private static final Clock CLOCK = Clock.fixed(Instant.parse("2026-09-04T03:00:00Z"), ZoneOffset.UTC);
    private static final String DEST = "oracle-health-sandbox";
    private static final String PATIENT_ID = "lab-configured-patient";
    private static final String SECRET = "projection-secret-token";

    @Mock
    private RoutingService routingService;

    @Test
    void completeProjectionWhenEveryResourceSucceedsIncludingEmptyBundle() {
        when(routingService.readPatient(eq(DEST), any(), eq(PATIENT_ID))).thenReturn(patient());
        when(routingService.searchConditions(eq(DEST), any(), eq(PATIENT_ID))).thenReturn(conditions(2));
        when(routingService.searchObservations(eq(DEST), any(), eq(PATIENT_ID))).thenReturn(new Bundle());
        when(routingService.searchDiagnosticReports(eq(DEST), any(), eq(PATIENT_ID))).thenReturn(reports(1));
        when(routingService.searchMedicationRequests(eq(DEST), any(), eq(PATIENT_ID))).thenReturn(medications(4));

        ClinicalProjectionResult result = assembler().assemble(DEST, token(), PATIENT_ID, allSupported());

        assertThat(result.outcome()).isEqualTo(ClinicalSnapshotOutcome.SNAPSHOT_COMPLETE);
        assertThat(result.contextSource()).isEqualTo(PatientContextSource.CONFIGURED);
        assertThat(result.generatedAt()).isEqualTo(Instant.parse("2026-09-04T03:00:00Z"));
        assertThat(result.patientStatus()).isEqualTo(ClinicalSnapshotResourceStatus.SUCCESS);
        assertThat(result.patient().resourceType()).isEqualTo("Patient");
        assertThat(result.conditions().status()).isEqualTo(ClinicalSnapshotResourceStatus.SUCCESS);
        assertThat(result.conditions().receivedCount()).isEqualTo(2);
        assertThat(result.conditions().retainedCount()).isEqualTo(2);
        assertThat(result.conditions().truncated()).isFalse();
        assertThat(result.observations().status()).isEqualTo(ClinicalSnapshotResourceStatus.SUCCESS);
        assertThat(result.observations().receivedCount()).isZero();
        assertThat(result.observations().retainedCount()).isZero();
        assertThat(result.observations().truncated()).isFalse();
        assertThat(result.diagnosticReports().retainedCount()).isEqualTo(1);
        assertThat(result.medicationRequests().retainedCount()).isEqualTo(4);
        assertThat(result.toString()).doesNotContain(PATIENT_ID);
        assertThat(result.toString()).doesNotContain(SECRET);
        assertThat(result.toString()).doesNotContain("active");
        verify(routingService).readPatient(eq(DEST), any(), eq(PATIENT_ID));
    }

    @Test
    void retainsFirstFiveOf1489AndMarksTruncated() {
        when(routingService.readPatient(eq(DEST), any(), eq(PATIENT_ID))).thenReturn(patient());
        when(routingService.searchConditions(eq(DEST), any(), eq(PATIENT_ID))).thenReturn(conditions(1489));
        when(routingService.searchObservations(eq(DEST), any(), eq(PATIENT_ID))).thenReturn(observations(6));
        when(routingService.searchDiagnosticReports(eq(DEST), any(), eq(PATIENT_ID))).thenReturn(reports(5));
        when(routingService.searchMedicationRequests(eq(DEST), any(), eq(PATIENT_ID))).thenReturn(medications(1));

        ClinicalProjectionResult result = assembler().assemble(DEST, token(), PATIENT_ID, allSupported());

        assertThat(result.outcome()).isEqualTo(ClinicalSnapshotOutcome.SNAPSHOT_COMPLETE);
        assertThat(result.conditions().receivedCount()).isEqualTo(1489);
        assertThat(result.conditions().retainedCount()).isEqualTo(5);
        assertThat(result.conditions().truncated()).isTrue();
        assertThat(result.conditions().items()).hasSize(5);
        assertThat(result.conditions().items())
                .extracting(RetainedCondition::clinicalStatus)
                .containsExactly("active", "active", "active", "active", "active");
        assertThat(result.observations().receivedCount()).isEqualTo(6);
        assertThat(result.observations().retainedCount()).isEqualTo(5);
        assertThat(result.observations().truncated()).isTrue();
        assertThat(result.diagnosticReports().receivedCount()).isEqualTo(5);
        assertThat(result.diagnosticReports().retainedCount()).isEqualTo(5);
        assertThat(result.diagnosticReports().truncated()).isFalse();
        assertThat(result.toString()).doesNotContain("secret-condition-");
        assertThat(result.toString()).doesNotContain(PATIENT_ID);
    }

    @Test
    void observationTimeoutIsPartialAndDoesNotEraseOtherSuccess() {
        when(routingService.readPatient(eq(DEST), any(), eq(PATIENT_ID))).thenReturn(patient());
        when(routingService.searchConditions(eq(DEST), any(), eq(PATIENT_ID))).thenReturn(conditions(1));
        when(routingService.searchObservations(eq(DEST), any(), eq(PATIENT_ID)))
                .thenThrow(FhirClientException.from(new FhirClientConnectionException(
                        "timed out", new SocketTimeoutException("Read timed out"))));
        when(routingService.searchDiagnosticReports(eq(DEST), any(), eq(PATIENT_ID))).thenReturn(reports(1));
        when(routingService.searchMedicationRequests(eq(DEST), any(), eq(PATIENT_ID))).thenReturn(medications(1));

        ClinicalProjectionResult result = assembler().assemble(DEST, token(), PATIENT_ID, allSupported());

        assertThat(result.outcome()).isEqualTo(ClinicalSnapshotOutcome.SNAPSHOT_PARTIAL);
        assertThat(result.conditions().status()).isEqualTo(ClinicalSnapshotResourceStatus.SUCCESS);
        assertThat(result.observations().status()).isEqualTo(ClinicalSnapshotResourceStatus.FAILED);
        assertThat(result.observations().receivedCount()).isNull();
        assertThat(result.observations().items()).isEmpty();
        assertThat(result.diagnosticReports().status()).isEqualTo(ClinicalSnapshotResourceStatus.SUCCESS);
        assertThat(result.toString()).doesNotContain("Read timed out");
    }

    @Test
    void medicationRequest403IsUnauthorizedPartial() {
        when(routingService.readPatient(eq(DEST), any(), eq(PATIENT_ID))).thenReturn(patient());
        when(routingService.searchConditions(eq(DEST), any(), eq(PATIENT_ID))).thenReturn(new Bundle());
        when(routingService.searchObservations(eq(DEST), any(), eq(PATIENT_ID))).thenReturn(new Bundle());
        when(routingService.searchDiagnosticReports(eq(DEST), any(), eq(PATIENT_ID))).thenReturn(new Bundle());
        when(routingService.searchMedicationRequests(eq(DEST), any(), eq(PATIENT_ID)))
                .thenThrow(FhirClientException.from(new ForbiddenOperationException("forbidden")));

        ClinicalProjectionResult result = assembler().assemble(DEST, token(), PATIENT_ID, allSupported());

        assertThat(result.outcome()).isEqualTo(ClinicalSnapshotOutcome.SNAPSHOT_PARTIAL);
        assertThat(result.medicationRequests().status()).isEqualTo(ClinicalSnapshotResourceStatus.UNAUTHORIZED);
        assertThat(result.medicationRequests().receivedCount()).isNull();
    }

    @Test
    void missingDiagnosticReportCapabilitySkipsThatHttp() {
        when(routingService.readPatient(eq(DEST), any(), eq(PATIENT_ID))).thenReturn(patient());
        when(routingService.searchConditions(eq(DEST), any(), eq(PATIENT_ID))).thenReturn(new Bundle());
        when(routingService.searchObservations(eq(DEST), any(), eq(PATIENT_ID))).thenReturn(new Bundle());
        when(routingService.searchMedicationRequests(eq(DEST), any(), eq(PATIENT_ID))).thenReturn(new Bundle());

        ClinicalProjectionResult result =
                assembler().assemble(DEST, token(), PATIENT_ID, without("DiagnosticReport"));

        assertThat(result.outcome()).isEqualTo(ClinicalSnapshotOutcome.SNAPSHOT_PARTIAL);
        assertThat(result.diagnosticReports().status()).isEqualTo(ClinicalSnapshotResourceStatus.UNAVAILABLE);
        verify(routingService, never()).searchDiagnosticReports(any(), any(), any());
    }

    @Test
    void patientReadFailureDoesNotSearchCollections() {
        when(routingService.readPatient(eq(DEST), any(), eq(PATIENT_ID)))
                .thenThrow(FhirClientException.from(new AuthenticationException()));

        ClinicalProjectionResult result = assembler().assemble(DEST, token(), PATIENT_ID, allSupported());

        assertThat(result.outcome()).isEqualTo(ClinicalSnapshotOutcome.SNAPSHOT_UNAVAILABLE);
        assertThat(result.patientStatus()).isEqualTo(ClinicalSnapshotResourceStatus.FAILED);
        assertThat(result.patient()).isNull();
        assertThat(result.conditions()).isNull();
        verify(routingService, never()).searchConditions(any(), any(), any());
        verify(routingService, never()).searchObservations(any(), any(), any());
        verify(routingService, never()).searchDiagnosticReports(any(), any(), any());
        verify(routingService, never()).searchMedicationRequests(any(), any(), any());
    }

    @Test
    void missingPatientReadCapabilityIsUnavailableWithoutHttp() {
        ClinicalProjectionResult result = assembler().assemble(DEST, token(), PATIENT_ID, without("Patient"));

        assertThat(result.outcome()).isEqualTo(ClinicalSnapshotOutcome.SNAPSHOT_UNAVAILABLE);
        assertThat(result.patientStatus()).isEqualTo(ClinicalSnapshotResourceStatus.UNAVAILABLE);
        verify(routingService, never()).readPatient(any(), any(), any());
        verify(routingService, never()).searchConditions(any(), any(), any());
    }

    private ClinicalProjectionAssembler assembler() {
        return new ClinicalProjectionAssembler(routingService, new RetentionCeiling(), CLOCK);
    }

    private static IssuedAccessTokenProvider token() {
        return new IssuedAccessTokenProvider(new AccessToken(SECRET, Instant.parse("2026-09-04T04:00:00Z")));
    }

    private static Patient patient() {
        Patient patient = new Patient();
        patient.setId(PATIENT_ID);
        return patient;
    }

    private static Bundle conditions(int count) {
        return entries(count, i -> {
            Condition condition = new Condition();
            condition.setId("secret-condition-" + i);
            condition.setCode(new CodeableConcept().setText("secret-diagnosis-" + i));
            condition.getClinicalStatus().addCoding(new Coding().setCode(i < 5 ? "active" : "resolved"));
            return condition;
        });
    }

    private static Bundle observations(int count) {
        return entries(count, i -> {
            Observation observation = new Observation();
            observation.setId("secret-obs-" + i);
            observation.setStatus(Observation.ObservationStatus.FINAL);
            return observation;
        });
    }

    private static Bundle reports(int count) {
        return entries(count, i -> {
            DiagnosticReport report = new DiagnosticReport();
            report.setId("secret-report-" + i);
            report.setStatus(DiagnosticReport.DiagnosticReportStatus.FINAL);
            return report;
        });
    }

    private static Bundle medications(int count) {
        return entries(count, i -> {
            MedicationRequest request = new MedicationRequest();
            request.setId("secret-med-" + i);
            request.setStatus(MedicationRequest.MedicationRequestStatus.ACTIVE);
            request.setIntent(MedicationRequest.MedicationRequestIntent.ORDER);
            return request;
        });
    }

    private static Bundle entries(int count, java.util.function.IntFunction<Resource> factory) {
        Bundle bundle = new Bundle();
        bundle.setType(Bundle.BundleType.SEARCHSET);
        for (int i = 0; i < count; i++) {
            bundle.addEntry().setResource(factory.apply(i));
        }
        return bundle;
    }

    private static FhirServerCapabilities allSupported() {
        return capabilities("Patient", "Condition", "Observation", "DiagnosticReport", "MedicationRequest");
    }

    private static FhirServerCapabilities without(String excluded) {
        return switch (excluded) {
            case "Patient" -> capabilities("Condition", "Observation", "DiagnosticReport", "MedicationRequest");
            case "DiagnosticReport" -> capabilities("Patient", "Condition", "Observation", "MedicationRequest");
            default -> throw new IllegalArgumentException(excluded);
        };
    }

    private static FhirServerCapabilities capabilities(String... types) {
        CapabilityStatement statement = new CapabilityStatement();
        statement.setFhirVersion(Enumerations.FHIRVersion._4_0_1);
        CapabilityStatement.CapabilityStatementRestComponent rest = statement.addRest();
        for (String type : types) {
            CapabilityStatement.CapabilityStatementRestResourceComponent resource = rest.addResource();
            resource.setType(type);
            if ("Patient".equals(type)) {
                resource.addInteraction().setCode(CapabilityStatement.TypeRestfulInteraction.READ);
            } else {
                resource.addInteraction().setCode(CapabilityStatement.TypeRestfulInteraction.SEARCHTYPE);
            }
        }
        return new FhirCapabilityDiscoveryService().interpret(DEST, statement);
    }
}

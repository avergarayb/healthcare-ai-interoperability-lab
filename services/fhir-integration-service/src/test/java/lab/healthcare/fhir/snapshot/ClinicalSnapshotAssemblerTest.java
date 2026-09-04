package lab.healthcare.fhir.snapshot;

import lab.healthcare.fhir.auth.AccessToken;
import lab.healthcare.fhir.auth.IssuedAccessTokenProvider;
import lab.healthcare.fhir.capability.FhirCapabilityDiscoveryService;
import lab.healthcare.fhir.capability.FhirServerCapabilities;
import lab.healthcare.fhir.exception.FhirClientException;
import lab.healthcare.fhir.patient.PatientContextSource;
import lab.healthcare.fhir.routing.RoutingService;

import ca.uhn.fhir.rest.client.exceptions.FhirClientConnectionException;
import ca.uhn.fhir.rest.server.exceptions.AuthenticationException;
import ca.uhn.fhir.rest.server.exceptions.ForbiddenOperationException;
import org.hl7.fhir.r4.model.Bundle;
import org.hl7.fhir.r4.model.CapabilityStatement;
import org.hl7.fhir.r4.model.Condition;
import org.hl7.fhir.r4.model.Enumerations;
import org.hl7.fhir.r4.model.Patient;
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
class ClinicalSnapshotAssemblerTest {

    private static final Clock CLOCK = Clock.fixed(Instant.parse("2026-09-04T03:00:00Z"), ZoneOffset.UTC);
    private static final String DEST = "oracle-health-sandbox";
    private static final String PATIENT_ID = "lab-configured-patient";
    private static final String SECRET = "snapshot-secret-token";

    @Mock
    private RoutingService routingService;

    @Test
    void completeSnapshotWhenEveryResourceSucceedsIncludingEmptyBundle() {
        when(routingService.readPatient(eq(DEST), any(), eq(PATIENT_ID))).thenReturn(new Patient());
        when(routingService.searchConditions(eq(DEST), any(), eq(PATIENT_ID))).thenReturn(entries(2));
        when(routingService.searchObservations(eq(DEST), any(), eq(PATIENT_ID))).thenReturn(new Bundle());
        when(routingService.searchDiagnosticReports(eq(DEST), any(), eq(PATIENT_ID))).thenReturn(entries(1));
        when(routingService.searchMedicationRequests(eq(DEST), any(), eq(PATIENT_ID))).thenReturn(entries(4));

        ClinicalSnapshotResult result = assembler().assemble(DEST, token(), PATIENT_ID, allSupported());

        assertThat(result.outcome()).isEqualTo(ClinicalSnapshotOutcome.SNAPSHOT_COMPLETE);
        assertThat(result.contextSource()).isEqualTo(PatientContextSource.CONFIGURED);
        assertThat(result.generatedAt()).isEqualTo(Instant.parse("2026-09-04T03:00:00Z"));
        assertThat(result.patientStatus()).isEqualTo(ClinicalSnapshotResourceStatus.SUCCESS);
        assertThat(result.conditionStatus()).isEqualTo(ClinicalSnapshotResourceStatus.SUCCESS);
        assertThat(result.conditionCount()).isEqualTo(2);
        assertThat(result.observationStatus()).isEqualTo(ClinicalSnapshotResourceStatus.SUCCESS);
        assertThat(result.observationCount()).isEqualTo(0);
        assertThat(result.diagnosticReportCount()).isEqualTo(1);
        assertThat(result.medicationRequestCount()).isEqualTo(4);
        assertThat(result.toString()).doesNotContain(PATIENT_ID);
        assertThat(result.toString()).doesNotContain(SECRET);
        verify(routingService).readPatient(eq(DEST), any(), eq(PATIENT_ID));
    }

    @Test
    void observationTimeoutIsPartialAndDoesNotEraseOtherSuccess() {
        when(routingService.readPatient(eq(DEST), any(), eq(PATIENT_ID))).thenReturn(new Patient());
        when(routingService.searchConditions(eq(DEST), any(), eq(PATIENT_ID))).thenReturn(entries(1));
        when(routingService.searchObservations(eq(DEST), any(), eq(PATIENT_ID)))
                .thenThrow(FhirClientException.from(new FhirClientConnectionException(
                        "timed out", new SocketTimeoutException("Read timed out"))));
        when(routingService.searchDiagnosticReports(eq(DEST), any(), eq(PATIENT_ID))).thenReturn(entries(1));
        when(routingService.searchMedicationRequests(eq(DEST), any(), eq(PATIENT_ID))).thenReturn(entries(1));

        ClinicalSnapshotResult result = assembler().assemble(DEST, token(), PATIENT_ID, allSupported());

        assertThat(result.outcome()).isEqualTo(ClinicalSnapshotOutcome.SNAPSHOT_PARTIAL);
        assertThat(result.conditionStatus()).isEqualTo(ClinicalSnapshotResourceStatus.SUCCESS);
        assertThat(result.observationStatus()).isEqualTo(ClinicalSnapshotResourceStatus.FAILED);
        assertThat(result.observationCount()).isNull();
        assertThat(result.diagnosticReportStatus()).isEqualTo(ClinicalSnapshotResourceStatus.SUCCESS);
        assertThat(result.toString()).doesNotContain("Read timed out");
    }

    @Test
    void medicationRequest403IsUnauthorizedPartial() {
        when(routingService.readPatient(eq(DEST), any(), eq(PATIENT_ID))).thenReturn(new Patient());
        when(routingService.searchConditions(eq(DEST), any(), eq(PATIENT_ID))).thenReturn(new Bundle());
        when(routingService.searchObservations(eq(DEST), any(), eq(PATIENT_ID))).thenReturn(new Bundle());
        when(routingService.searchDiagnosticReports(eq(DEST), any(), eq(PATIENT_ID))).thenReturn(new Bundle());
        when(routingService.searchMedicationRequests(eq(DEST), any(), eq(PATIENT_ID)))
                .thenThrow(FhirClientException.from(new ForbiddenOperationException("forbidden")));

        ClinicalSnapshotResult result = assembler().assemble(DEST, token(), PATIENT_ID, allSupported());

        assertThat(result.outcome()).isEqualTo(ClinicalSnapshotOutcome.SNAPSHOT_PARTIAL);
        assertThat(result.medicationRequestStatus()).isEqualTo(ClinicalSnapshotResourceStatus.UNAUTHORIZED);
        assertThat(result.medicationRequestCount()).isNull();
    }

    @Test
    void missingDiagnosticReportCapabilitySkipsThatHttp() {
        when(routingService.readPatient(eq(DEST), any(), eq(PATIENT_ID))).thenReturn(new Patient());
        when(routingService.searchConditions(eq(DEST), any(), eq(PATIENT_ID))).thenReturn(new Bundle());
        when(routingService.searchObservations(eq(DEST), any(), eq(PATIENT_ID))).thenReturn(new Bundle());
        when(routingService.searchMedicationRequests(eq(DEST), any(), eq(PATIENT_ID))).thenReturn(new Bundle());

        ClinicalSnapshotResult result =
                assembler().assemble(DEST, token(), PATIENT_ID, without("DiagnosticReport"));

        assertThat(result.outcome()).isEqualTo(ClinicalSnapshotOutcome.SNAPSHOT_PARTIAL);
        assertThat(result.diagnosticReportStatus()).isEqualTo(ClinicalSnapshotResourceStatus.UNAVAILABLE);
        verify(routingService, never()).searchDiagnosticReports(any(), any(), any());
    }

    @Test
    void patientReadFailureDoesNotSearchCollections() {
        when(routingService.readPatient(eq(DEST), any(), eq(PATIENT_ID)))
                .thenThrow(FhirClientException.from(new AuthenticationException()));

        ClinicalSnapshotResult result = assembler().assemble(DEST, token(), PATIENT_ID, allSupported());

        assertThat(result.outcome()).isEqualTo(ClinicalSnapshotOutcome.SNAPSHOT_UNAVAILABLE);
        assertThat(result.patientStatus()).isEqualTo(ClinicalSnapshotResourceStatus.FAILED);
        assertThat(result.conditionStatus()).isNull();
        verify(routingService, never()).searchConditions(any(), any(), any());
        verify(routingService, never()).searchObservations(any(), any(), any());
        verify(routingService, never()).searchDiagnosticReports(any(), any(), any());
        verify(routingService, never()).searchMedicationRequests(any(), any(), any());
    }

    @Test
    void missingPatientReadCapabilityIsUnavailableWithoutHttp() {
        ClinicalSnapshotResult result = assembler().assemble(DEST, token(), PATIENT_ID, without("Patient"));

        assertThat(result.outcome()).isEqualTo(ClinicalSnapshotOutcome.SNAPSHOT_UNAVAILABLE);
        assertThat(result.patientStatus()).isEqualTo(ClinicalSnapshotResourceStatus.UNAVAILABLE);
        verify(routingService, never()).readPatient(any(), any(), any());
        verify(routingService, never()).searchConditions(any(), any(), any());
    }

    private ClinicalSnapshotAssembler assembler() {
        return new ClinicalSnapshotAssembler(routingService, CLOCK);
    }

    private static IssuedAccessTokenProvider token() {
        return new IssuedAccessTokenProvider(new AccessToken(SECRET, Instant.parse("2026-09-04T04:00:00Z")));
    }

    private static Bundle entries(int count) {
        Bundle bundle = new Bundle();
        bundle.setType(Bundle.BundleType.SEARCHSET);
        for (int i = 0; i < count; i++) {
            Condition condition = new Condition();
            condition.setId("secret-condition-" + i);
            bundle.addEntry().setResource(condition);
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

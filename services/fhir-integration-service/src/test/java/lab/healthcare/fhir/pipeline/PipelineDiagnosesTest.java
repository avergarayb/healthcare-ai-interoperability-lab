package lab.healthcare.fhir.pipeline;

import lab.healthcare.fhir.modelboundary.ModelBoundaryContract;
import lab.healthcare.fhir.patient.PatientContextSource;
import lab.healthcare.fhir.projection.ClinicalProjectionResult;
import lab.healthcare.fhir.projection.ProjectedCollection;
import lab.healthcare.fhir.projection.RetainedCondition;
import lab.healthcare.fhir.projection.RetainedDiagnosticReport;
import lab.healthcare.fhir.projection.RetainedMedicationRequest;
import lab.healthcare.fhir.projection.RetainedObservation;
import lab.healthcare.fhir.projection.RetainedPatient;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotOutcome;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotResourceStatus;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotResult;

import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class PipelineDiagnosesTest {

    private static final Instant GENERATED_AT = Instant.parse("2026-09-12T20:00:00Z");

    @Test
    void completeEpicProjectionIsSuccessAndMedicationNotRequested() {
        PipelineDiagnosis diagnosis = PipelineDiagnoses.fromProjection(completeEpic());

        assertThat(diagnosis.overall()).isEqualTo(PipelineStageStatus.SUCCESS);
        assertThat(diagnosis.contractValid()).isTrue();
        assertThat(diagnosis.usable()).isTrue();
        assertThat(stage(diagnosis, "medicationRequests").status()).isEqualTo(PipelineStageStatus.NOT_REQUESTED);
        assertThat(diagnosis.toString()).doesNotContain("active");
        assertThat(diagnosis.toString()).doesNotContain("access_token");
    }

    @Test
    void observationTimeoutIsPartialAndUsable() {
        ClinicalProjectionResult projection = new ClinicalProjectionResult(
                ClinicalSnapshotOutcome.SNAPSHOT_PARTIAL,
                "epic-sandbox",
                PatientContextSource.CONFIGURED,
                GENERATED_AT,
                ClinicalSnapshotResourceStatus.SUCCESS,
                new RetainedPatient("Patient"),
                ProjectedCollection.retained(1, 1, false, List.of(new RetainedCondition("Condition", "active"))),
                ProjectedCollection.failed(ClinicalSnapshotResourceStatus.TIMEOUT),
                ProjectedCollection.retained(
                        1, 1, false, List.of(new RetainedDiagnosticReport("DiagnosticReport", "final"))),
                null,
                "Controlled clinical projection is partial");

        PipelineDiagnosis diagnosis = PipelineDiagnoses.fromProjection(projection);

        assertThat(diagnosis.overall()).isEqualTo(PipelineStageStatus.PARTIAL);
        assertThat(diagnosis.usable()).isTrue();
        assertThat(diagnosis.contractValid()).isTrue();
        assertThat(stage(diagnosis, "observations").status()).isEqualTo(PipelineStageStatus.TIMEOUT);
        assertThat(stage(diagnosis, "observations").error().code()).isEqualTo(PipelineErrorCodes.FHIR_TIMEOUT);
        assertThat(stage(diagnosis, "observations").error().retryable()).isTrue();
    }

    @Test
    void patientFailureIsFailedAndNotUsable() {
        PipelineDiagnosis diagnosis = PipelineDiagnoses.fromProjection(ClinicalProjectionResult.unavailable(
                "oracle-health-sandbox",
                GENERATED_AT,
                ClinicalSnapshotResourceStatus.FAILED,
                "Patient context could not be established"));

        assertThat(diagnosis.overall()).isEqualTo(PipelineStageStatus.FAILED);
        assertThat(diagnosis.usable()).isFalse();
        assertThat(diagnosis.contractValid()).isFalse();
        assertThat(stage(diagnosis, "patient").critical()).isTrue();
    }

    @Test
    void completeOracleProjectionKeepsMedicationRequests() {
        ClinicalProjectionResult projection = new ClinicalProjectionResult(
                ClinicalSnapshotOutcome.SNAPSHOT_COMPLETE,
                "oracle-health-sandbox",
                PatientContextSource.CONFIGURED,
                GENERATED_AT,
                ClinicalSnapshotResourceStatus.SUCCESS,
                new RetainedPatient("Patient"),
                ProjectedCollection.retained(1, 1, false, List.of(new RetainedCondition("Condition", "active"))),
                ProjectedCollection.retained(1, 1, false, List.of(new RetainedObservation("Observation", "final"))),
                ProjectedCollection.retained(
                        1, 1, false, List.of(new RetainedDiagnosticReport("DiagnosticReport", "final"))),
                ProjectedCollection.retained(
                        1, 1, false, List.of(new RetainedMedicationRequest("MedicationRequest", "active", "order"))),
                "Controlled clinical projection succeeded");

        PipelineDiagnosis diagnosis = PipelineDiagnoses.fromProjection(projection);

        assertThat(diagnosis.overall()).isEqualTo(PipelineStageStatus.SUCCESS);
        assertThat(diagnosis.contractValid()).isTrue();
        assertThat(stage(diagnosis, "medicationRequests").status()).isEqualTo(PipelineStageStatus.SUCCESS);
        assertThat(diagnosis.toString()).doesNotContain("active");
        assertThat(diagnosis.toString()).doesNotContain("order");
    }

    @Test
    void missingCapabilityIsNotAvailableAndPartial() {
        ClinicalProjectionResult projection = new ClinicalProjectionResult(
                ClinicalSnapshotOutcome.SNAPSHOT_PARTIAL,
                "oracle-health-sandbox",
                PatientContextSource.CONFIGURED,
                GENERATED_AT,
                ClinicalSnapshotResourceStatus.SUCCESS,
                new RetainedPatient("Patient"),
                ProjectedCollection.retained(0, 0, false, List.of()),
                ProjectedCollection.retained(0, 0, false, List.of()),
                ProjectedCollection.unavailable(),
                ProjectedCollection.retained(0, 0, false, List.of()),
                "Controlled clinical projection is partial");

        PipelineDiagnosis diagnosis = PipelineDiagnoses.fromProjection(projection);

        assertThat(diagnosis.overall()).isEqualTo(PipelineStageStatus.PARTIAL);
        assertThat(stage(diagnosis, "diagnosticReports").status()).isEqualTo(PipelineStageStatus.NOT_AVAILABLE);
        assertThat(stage(diagnosis, "medicationRequests").status()).isEqualTo(PipelineStageStatus.SUCCESS);
    }

    @Test
    void invalidContractIsRejected() {
        PipelineDiagnosis diagnosis = PipelineDiagnoses.fromContract(new ModelBoundaryContract(
                "v2",
                "epic-sandbox",
                PatientContextSource.CONFIGURED,
                GENERATED_AT,
                ClinicalSnapshotOutcome.SNAPSHOT_COMPLETE,
                null,
                null,
                null,
                null,
                null));

        assertThat(diagnosis.overall()).isEqualTo(PipelineStageStatus.REJECTED);
        assertThat(diagnosis.contractValid()).isFalse();
        assertThat(diagnosis.usable()).isFalse();
        assertThat(stage(diagnosis, "agentStub").error().code()).isEqualTo(PipelineErrorCodes.AGENT_STUB_REJECTED);
    }

    @Test
    void snapshotOmitsMedicationAsNotRequested() {
        PipelineDiagnosis diagnosis = PipelineDiagnoses.fromSnapshot(new ClinicalSnapshotResult(
                ClinicalSnapshotOutcome.SNAPSHOT_COMPLETE,
                "epic-sandbox",
                PatientContextSource.CONFIGURED,
                GENERATED_AT,
                ClinicalSnapshotResourceStatus.SUCCESS,
                ClinicalSnapshotResourceStatus.SUCCESS,
                1,
                ClinicalSnapshotResourceStatus.SUCCESS,
                5,
                ClinicalSnapshotResourceStatus.SUCCESS,
                5,
                null,
                null,
                "Controlled clinical snapshot succeeded"));

        assertThat(diagnosis.overall()).isEqualTo(PipelineStageStatus.SUCCESS);
        assertThat(stage(diagnosis, "medicationRequests").status()).isEqualTo(PipelineStageStatus.NOT_REQUESTED);
    }

    @Test
    void authenticationRequiredIsAuthenticationFailed() {
        PipelineDiagnosis diagnosis =
                PipelineDiagnoses.fromProjection(ClinicalProjectionResult.authenticationRequired(
                        "epic-sandbox", "No usable access token"));

        assertThat(diagnosis.overall()).isEqualTo(PipelineStageStatus.AUTHENTICATION_FAILED);
        assertThat(diagnosis.toString()).doesNotContain("access_token");
        assertThat(SafePipelineLog.line(diagnosis, "epic-sandbox")).doesNotContain("Bearer");
    }

    private static ClinicalProjectionResult completeEpic() {
        return new ClinicalProjectionResult(
                ClinicalSnapshotOutcome.SNAPSHOT_COMPLETE,
                "epic-sandbox",
                PatientContextSource.CONFIGURED,
                GENERATED_AT,
                ClinicalSnapshotResourceStatus.SUCCESS,
                new RetainedPatient("Patient"),
                ProjectedCollection.retained(1, 1, false, List.of(new RetainedCondition("Condition", "active"))),
                ProjectedCollection.retained(1, 1, false, List.of(new RetainedObservation("Observation", "final"))),
                ProjectedCollection.retained(
                        1, 1, false, List.of(new RetainedDiagnosticReport("DiagnosticReport", "final"))),
                null,
                "Controlled clinical projection succeeded");
    }

    private static PipelineStageDiagnosis stage(PipelineDiagnosis diagnosis, String name) {
        return diagnosis.stages().stream()
                .filter(stage -> name.equals(stage.stage()))
                .findFirst()
                .orElseThrow();
    }
}

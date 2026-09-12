package lab.healthcare.fhir.pipeline;

import lab.healthcare.fhir.agentstub.AgentStub;
import lab.healthcare.fhir.modelboundary.BoundaryCollection;
import lab.healthcare.fhir.modelboundary.ModelBoundaryContract;
import lab.healthcare.fhir.modelboundary.ModelBoundaryMapper;
import lab.healthcare.fhir.projection.ClinicalProjectionResult;
import lab.healthcare.fhir.projection.ProjectedCollection;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotOutcome;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotResourceStatus;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotResult;

import java.util.ArrayList;
import java.util.List;

/**
 * Builds a pipeline diagnosis from existing snapshot/projection/contract
 * results. Does not fetch FHIR or call a model.
 */
public final class PipelineDiagnoses {

    private PipelineDiagnoses() {
    }

    public static PipelineDiagnosis fromProjection(ClinicalProjectionResult projection) {
        if (projection == null) {
            return rejected("projection", PipelineErrorCodes.PROJECTION_VALIDATION_FAILED, "Clinical projection is missing");
        }
        List<PipelineStageDiagnosis> stages = new ArrayList<>();
        stages.add(patient(projection.outcome(), projection.patientStatus()));
        stages.add(collection("conditions", projection.conditions()));
        stages.add(collection("observations", projection.observations()));
        stages.add(collection("diagnosticReports", projection.diagnosticReports()));
        stages.add(collection("medicationRequests", projection.medicationRequests()));
        if (projection.outcome() == ClinicalSnapshotOutcome.SNAPSHOT_UNAVAILABLE
                || projection.outcome() == ClinicalSnapshotOutcome.AUTHENTICATION_REQUIRED
                || projection.outcome() == ClinicalSnapshotOutcome.PATIENT_CONTEXT_NOT_CONFIGURED) {
            stages.add(PipelineStageDiagnosis.of(
                    "projection", PipelineStatuses.ofOutcome(projection.outcome()), true));
            PipelineStageStatus overall = PipelineAggregator.overall(stages);
            return new PipelineDiagnosis(overall, false, false, stages);
        }
        stages.add(PipelineStageDiagnosis.of("projection", PipelineStageStatus.SUCCESS, true));
        return withContract(stages, ModelBoundaryMapper.from(projection));
    }

    public static PipelineDiagnosis fromSnapshot(ClinicalSnapshotResult snapshot) {
        if (snapshot == null) {
            return rejected("snapshot", PipelineErrorCodes.PROJECTION_VALIDATION_FAILED, "Clinical snapshot is missing");
        }
        List<PipelineStageDiagnosis> stages = new ArrayList<>();
        stages.add(patient(snapshot.outcome(), snapshot.patientStatus()));
        stages.add(snapshotCollection("conditions", snapshot.conditionStatus(), snapshot.conditionCount()));
        stages.add(snapshotCollection("observations", snapshot.observationStatus(), snapshot.observationCount()));
        stages.add(snapshotCollection("diagnosticReports", snapshot.diagnosticReportStatus(), snapshot.diagnosticReportCount()));
        stages.add(snapshotCollection(
                "medicationRequests", snapshot.medicationRequestStatus(), snapshot.medicationRequestCount()));
        stages.add(PipelineStageDiagnosis.of("snapshot", PipelineStatuses.ofOutcome(snapshot.outcome()), true));
        PipelineStageStatus overall = PipelineAggregator.overall(stages);
        boolean usable = PipelineAggregator.usable(overall);
        return new PipelineDiagnosis(overall, usable, usable, stages);
    }

    public static PipelineDiagnosis fromContract(ModelBoundaryContract contract) {
        List<PipelineStageDiagnosis> stages = new ArrayList<>();
        if (contract == null) {
            return rejected("contract", PipelineErrorCodes.MODEL_BOUNDARY_REJECTED, "Model boundary contract is missing");
        }
        stages.add(patient(contract.outcome(), contract.patient() == null ? null : contract.patient().status()));
        stages.add(boundaryCollection("conditions", contract.conditions()));
        stages.add(boundaryCollection("observations", contract.observations()));
        stages.add(boundaryCollection("diagnosticReports", contract.diagnosticReports()));
        stages.add(boundaryCollection("medicationRequests", contract.medicationRequests()));
        if (contract.outcome() == ClinicalSnapshotOutcome.SNAPSHOT_UNAVAILABLE
                || contract.outcome() == ClinicalSnapshotOutcome.AUTHENTICATION_REQUIRED
                || contract.outcome() == ClinicalSnapshotOutcome.PATIENT_CONTEXT_NOT_CONFIGURED) {
            stages.add(PipelineStageDiagnosis.of("contract", PipelineStatuses.ofOutcome(contract.outcome()), true));
            PipelineStageStatus overall = PipelineAggregator.overall(stages);
            return new PipelineDiagnosis(overall, false, false, stages);
        }
        return withContract(stages, contract);
    }

    private static PipelineDiagnosis withContract(List<PipelineStageDiagnosis> stages, ModelBoundaryContract contract) {
        try {
            AgentStub.observe(contract);
            stages.add(PipelineStageDiagnosis.of("contract", PipelineStageStatus.SUCCESS, true));
            stages.add(PipelineStageDiagnosis.of("agentStub", PipelineStageStatus.SUCCESS, true));
            PipelineStageStatus overall = PipelineAggregator.overall(stages);
            return new PipelineDiagnosis(overall, true, PipelineAggregator.usable(overall), stages);
        } catch (RuntimeException ex) {
            PipelineErrorInfo error = new PipelineErrorInfo(
                    PipelineErrorCodes.AGENT_STUB_REJECTED,
                    PipelineStageStatus.REJECTED.name(),
                    false,
                    "Agent stub rejected the model boundary contract",
                    null);
            stages.add(new PipelineStageDiagnosis(
                    "agentStub", PipelineStageStatus.REJECTED, true, error, null, null, null, null));
            return new PipelineDiagnosis(PipelineStageStatus.REJECTED, false, false, stages);
        }
    }

    private static PipelineDiagnosis rejected(String stage, String code, String message) {
        PipelineErrorInfo error = new PipelineErrorInfo(code, PipelineStageStatus.REJECTED.name(), false, message, null);
        PipelineStageDiagnosis diagnosis =
                new PipelineStageDiagnosis(stage, PipelineStageStatus.REJECTED, true, error, null, null, null, null);
        return new PipelineDiagnosis(PipelineStageStatus.REJECTED, false, false, List.of(diagnosis));
    }

    private static PipelineStageDiagnosis patient(
            ClinicalSnapshotOutcome outcome, ClinicalSnapshotResourceStatus patientStatus) {
        if (outcome == ClinicalSnapshotOutcome.AUTHENTICATION_REQUIRED) {
            return new PipelineStageDiagnosis(
                    "patient",
                    PipelineStageStatus.AUTHENTICATION_FAILED,
                    true,
                    PipelineStatuses.errorFor(ClinicalSnapshotResourceStatus.UNAUTHORIZED),
                    null,
                    null,
                    null,
                    null);
        }
        if (outcome == ClinicalSnapshotOutcome.PATIENT_CONTEXT_NOT_CONFIGURED) {
            return new PipelineStageDiagnosis(
                    "patient",
                    PipelineStageStatus.VALIDATION_FAILED,
                    true,
                    new PipelineErrorInfo(
                            PipelineErrorCodes.PROJECTION_VALIDATION_FAILED,
                            PipelineStageStatus.VALIDATION_FAILED.name(),
                            false,
                            "Patient context is not configured",
                            null),
                    null,
                    null,
                    null,
                    null);
        }
        if (patientStatus == ClinicalSnapshotResourceStatus.FAILED
                || (patientStatus == null && outcome == ClinicalSnapshotOutcome.SNAPSHOT_UNAVAILABLE)) {
            return new PipelineStageDiagnosis(
                    "patient",
                    PipelineStageStatus.FAILED,
                    true,
                    PipelineStatuses.errorFor(ClinicalSnapshotResourceStatus.FAILED),
                    null,
                    null,
                    null,
                    null);
        }
        return new PipelineStageDiagnosis(
                "patient",
                PipelineStatuses.ofResource(patientStatus),
                true,
                PipelineStatuses.errorFor(patientStatus),
                null,
                null,
                null,
                null);
    }

    private static PipelineStageDiagnosis collection(String stage, ProjectedCollection<?> collection) {
        if (collection == null) {
            return PipelineStageDiagnosis.of(stage, PipelineStageStatus.NOT_REQUESTED, false);
        }
        return PipelineStageDiagnosis.collection(
                stage,
                PipelineStatuses.ofResource(collection.status()),
                collection.receivedCount(),
                collection.retainedCount(),
                collection.truncated(),
                PipelineStatuses.errorFor(collection.status()));
    }

    private static PipelineStageDiagnosis snapshotCollection(
            String stage, ClinicalSnapshotResourceStatus status, Integer count) {
        if (status == null && count == null) {
            return PipelineStageDiagnosis.of(stage, PipelineStageStatus.NOT_REQUESTED, false);
        }
        return PipelineStageDiagnosis.collection(
                stage, PipelineStatuses.ofResource(status), count, null, null, PipelineStatuses.errorFor(status));
    }

    private static PipelineStageDiagnosis boundaryCollection(String stage, BoundaryCollection<?> collection) {
        if (collection == null) {
            return PipelineStageDiagnosis.of(stage, PipelineStageStatus.NOT_REQUESTED, false);
        }
        return PipelineStageDiagnosis.collection(
                stage,
                PipelineStatuses.ofResource(collection.status()),
                collection.receivedCount(),
                collection.retainedCount(),
                collection.truncated(),
                PipelineStatuses.errorFor(collection.status()));
    }
}
